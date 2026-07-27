from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.players.avatar import normalize_avatar_recipe


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
    nickname = models.CharField(max_length=24)
    avatar_recipe = models.JSONField(default=dict)
    balance_cents = models.BigIntegerField(default=10_000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("nickname"), name="players_unique_nickname_ci"),
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
