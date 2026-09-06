from typing import ClassVar

from django.db import models


class ClipboardEntry(models.Model):
    objects: ClassVar[models.Manager]
    id = models.CharField(max_length=32, primary_key=True)
    text = models.TextField()
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("created_at", "id")
