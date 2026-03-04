from rest_framework import serializers
from api.models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "sources", "cached", "latency_ms", "model_name", "created_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ["session_id", "created_at", "updated_at", "message_count", "messages"]
        read_only_fields = fields


class ChatRequestSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000, min_length=1)
    session_id = serializers.UUIDField(required=False, allow_null=True)
    stream = serializers.BooleanField(default=False)
