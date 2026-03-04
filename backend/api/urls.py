from django.urls import path
from api.views import chat, chat_stream, health, conversation_history

urlpatterns = [
    path("chat/", chat, name="chat"),
    path("chat/stream/", chat_stream, name="chat-stream"),
    path("health/", health, name="health"),
    path("conversation/<uuid:session_id>/", conversation_history, name="conversation-history"),
]
