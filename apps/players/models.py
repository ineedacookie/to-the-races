from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class Device(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.token)


class Player(models.Model):
    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name="player")
    nickname = models.CharField(max_length=24)
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
