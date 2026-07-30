from __future__ import annotations

import secrets
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.players.avatar import normalize_avatar_recipe


def generate_api_key() -> str:
    return f"ttr_{secrets.token_urlsafe(32)}"


class Device(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    player = models.ForeignKey(
        "Player",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="devices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.token)


class Player(models.Model):
    class ReplayPreference(models.TextChoices):
        ASK = "ask", "Ask after each race"
        ALWAYS_WATCH = "always_watch", "Always watch"
        ALWAYS_SKIP = "always_skip", "Always skip"

    nickname = models.CharField(max_length=24)
    api_key = models.CharField(
        max_length=64,
        unique=True,
        default=generate_api_key,
        editable=False,
    )
    avatar_recipe = models.JSONField(default=dict)
    replay_preference = models.CharField(
        max_length=16,
        choices=ReplayPreference.choices,
        default=ReplayPreference.ASK,
        db_default=ReplayPreference.ASK,
    )
    balance_cents = models.BigIntegerField(default=20_000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("nickname"), name="players_unique_nickname_ci"),
            models.CheckConstraint(
                condition=models.Q(balance_cents__gte=0),
                name="players_balance_non_negative",
            ),
        ]
        ordering = ["nickname"]

    def __str__(self) -> str:
        return self.nickname

    def clean(self) -> None:
        nickname = " ".join(self.nickname.split()).strip()
        if len(nickname) < 2:
            raise ValidationError({"nickname": "Nickname must be at least 2 characters."})
        if not all(character.isalnum() or character in {" ", "-", "_"} for character in nickname):
            raise ValidationError(
                {"nickname": "Use only letters, numbers, spaces, hyphens, and underscores."}
            )
        self.nickname = nickname
        self.avatar_recipe = normalize_avatar_recipe(
            self.avatar_recipe,
            seed=self.pk or 0,
        )
