"""
API Views
- POST /api/chat/         → RAG query (non-streaming)
- GET  /api/chat/stream/  → RAG query (Server-Sent Events streaming)
- GET  /api/health/       → Service health check
- GET  /api/conversation/<session_id>/ → Conversation history
"""
import logging
import time

from django.http import StreamingHttpResponse
from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from api.models import Conversation, Message
from api.serializers import ChatRequestSerializer, ConversationSerializer
from rag import get_pipeline

logger = logging.getLogger("api")


def _get_or_create_conversation(session_id, request) -> Conversation:
    if session_id:
        conv, _ = Conversation.objects.get_or_create(
            session_id=session_id,
            defaults={
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:512],
            },
        )
    else:
        conv = Conversation.objects.create(
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
        )
    return conv


@api_view(["POST"])
def chat(request):
    """
    Main RAG chat endpoint.
    POST { "question": "...", "session_id": "..." (optional) }
    """
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    question = serializer.validated_data["question"]
    session_id = serializer.validated_data.get("session_id")

    # Conversation persistence
    conv = _get_or_create_conversation(session_id, request)
    Message.objects.create(conversation=conv, role=Message.Role.USER, content=question)
    conv.message_count += 1
    conv.save(update_fields=["message_count", "updated_at"])

    # RAG query
    start = time.time()
    pipeline = get_pipeline()

    # Check Redis cache first
    cache_key = f"rag:{hash(question)}"
    cached_answer = cache.get(cache_key)

    if cached_answer:
        rag_result = cached_answer
        rag_result["cached"] = True
    else:
        rag_response = pipeline.query(question)
        rag_result = {
            "answer": rag_response.answer,
            "sources": rag_response.sources,
            "cached": rag_response.cached,
            "model": rag_response.model,
            "latency_s": rag_response.latency_s,
            "error": rag_response.error,
        }
        if not rag_response.error:
            cache.set(cache_key, rag_result, timeout=3600)

    latency_ms = int((time.time() - start) * 1000)

    # Persist assistant message
    Message.objects.create(
        conversation=conv,
        role=Message.Role.ASSISTANT,
        content=rag_result["answer"],
        sources=rag_result.get("sources", []),
        cached=rag_result.get("cached", False),
        latency_ms=latency_ms,
        model_name=rag_result.get("model", ""),
    )
    conv.message_count += 1
    conv.save(update_fields=["message_count", "updated_at"])

    logger.info(
        "Chat | session=%s latency=%dms cached=%s",
        conv.session_id,
        latency_ms,
        rag_result.get("cached"),
    )

    return Response(
        {
            "answer": rag_result["answer"],
            "sources": rag_result.get("sources", []),
            "session_id": str(conv.session_id),
            "cached": rag_result.get("cached", False),
            "latency_ms": latency_ms,
            "model": rag_result.get("model", ""),
            "error": rag_result.get("error"),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
def chat_stream(request):
    """
    Streaming RAG endpoint using Server-Sent Events.
    GET /api/chat/stream/?question=...&session_id=...
    """
    question = request.query_params.get("question", "").strip()
    if not question:
        return Response({"error": "question is required"}, status=400)

    pipeline = get_pipeline()

    def event_stream():
        yield "retry: 3000\n\n"
        for chunk in pipeline.stream(question):
            yield chunk

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["GET"])
def health(request):
    """Health check for Docker/load balancer."""
    pipeline = get_pipeline()
    ollama_healthy = pipeline.llm_client.is_healthy()

    return Response(
        {
            "status": "ok" if ollama_healthy else "degraded",
            "services": {
                "django": "ok",
                "ollama": "ok" if ollama_healthy else "unreachable",
                "faiss": "ok" if pipeline.vector_store.index is not None else "not_loaded",
            },
        },
        status=200 if ollama_healthy else 503,
    )


@api_view(["GET"])
def conversation_history(request, session_id):
    """Retrieve full conversation history by session_id."""
    try:
        conv = Conversation.objects.prefetch_related("messages").get(session_id=session_id)
    except Conversation.DoesNotExist:
        return Response({"error": "Conversation not found"}, status=404)

    serializer = ConversationSerializer(conv)
    return Response(serializer.data)
