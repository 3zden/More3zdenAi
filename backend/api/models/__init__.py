"""
Django Models
- Conversation: a chat session (identified by session_id)
- Message: a single turn (user or assistant) within a conversation
"""
import uuid
from django.db import models


class Conversation(models.Model):
    """A chat session."""
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    message_count = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation {self.session_id} ({self.message_count} msgs)"


class Message(models.Model):
    """A single message turn in a conversation."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # RAG metadata
    sources = models.JSONField(default=list, blank=True)
    cached = models.BooleanField(default=False)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    model_name = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"
