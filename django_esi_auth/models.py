from django.contrib.auth.models import AbstractUser
from django.db import models

from . import choices


class DynamicObject:
    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, value)


class EveUser(AbstractUser):
    character_id = models.IntegerField(blank=True, null=True)
    character_name = models.CharField(max_length=255, blank=True, null=True)
    character_owner_hash = models.CharField(max_length=255, blank=True, null=True)
    corporation_id = models.IntegerField(blank=True, null=True)
    alliance_id = models.IntegerField(blank=True, null=True)
    last_access_check = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return str(self.character_name)


class EveEntity(models.Model):
    eve_entity_id = models.IntegerField(null=False, blank=False)
    eve_entity_type = models.CharField(
        null=False, blank=False, choices=choices.EVE_ENTITY_TYPE
    )
    eve_entity_name = models.CharField(null=False, blank=False)

    def __str__(self):
        return str(self.eve_entity_name)

    class Meta:
        verbose_name_plural = "Eve Entities"


class LoginAccessRight(models.Model):
    entity = models.ForeignKey(EveEntity, models.CASCADE)

    class Meta:
        verbose_name_plural = "Login Access Rights"
