import base64
import datetime
import json
from importlib import import_module
from typing import Dict, Any, Union, List

import pytz
import requests
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from jwcrypto.jwk import JWKSet
from jwcrypto.jwt import JWT

from . import signals
from .choices import EveEntityTypeEnum


class EveUser(AbstractUser):
    character_id = models.IntegerField(blank=True, null=True)
    character_name = models.CharField(max_length=255, blank=True, null=True)
    character_owner_hash = models.CharField(max_length=255, blank=True, null=True)
    corporation_id = models.IntegerField(blank=True, null=True)
    alliance_id = models.IntegerField(blank=True, null=True)
    last_access_check = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return str(self.character_name)


class EveEntityManager(models.Manager):

    def get_unknown_searchable_ids(self) -> List[int]:
        return list(
            self.filter(eve_entity_name="Unknown")
            .exclude(eve_entity_type=EveEntityTypeEnum.STRUCTURE)
            .exclude(eve_entity_id=0)
            .values_list("eve_entity_id", flat=True)
        )

    def get_uknown_structure_ids(self) -> List[int]:
        return list(
            self.filter(eve_entity_name="Unknown", eve_entity_type=EveEntityTypeEnum.STRUCTURE)
            .exclude(eve_entity_id=0)
            .values_list("eve_entity_id", flat=True)
        )

    def update_entities_from_esi(self, esi_data) -> List["EveEntity"]:
        entities_by_id = {e["id"]: e for e in esi_data}
        instances_to_update = []

        for entity in self.filter(eve_entity_id__in=entities_by_id.keys()):
            entity.eve_entity_name = entities_by_id[entity.eve_entity_id]["name"]
            entity.eve_entity_type = entities_by_id[entity.eve_entity_id]["category"]
            instances_to_update.append(entity)

        self.bulk_update(instances_to_update, ["eve_entity_name", "eve_entity_type"])
        return instances_to_update

    def update_entity_name(self, id: int, name: str) -> "EveEntity":
        try:
            entity = self.get(eve_entity_id=id)
            entity.eve_entity_name = name
            entity.save()
        except self.model.DoesNotExist:
            entity = None

        return entity

    def update_unknowns(self, tokens: List["Token"]) -> List["EveEntity"]:
        results = []
        unknown_searchable_ids = self.get_unknown_searchable_ids()
        if unknown_searchable_ids:
            public_client = getattr(import_module("django_esi_auth.client"), "ESIClient")()
            response = public_client.get_names(unknown_searchable_ids)
            results.extend(self.update_entities_from_esi(response.data))

        if tokens:
            for token in tokens:
                structure_ids = self.get_uknown_structure_ids()
                if structure_ids:
                    client = getattr(import_module("django_esi_auth.client"), "ESIClient")(token)
                    for structure_id in structure_ids:
                        response = client.get_structure(structure_id=structure_id)
                        if response.data:
                            results.append(self.update_entity_name(structure_id, response.data[0]["name"]))

        return results


class EveEntity(models.Model):
    eve_entity_id = models.BigIntegerField()
    eve_entity_type = models.CharField(
        null=False,
        blank=False,
        choices=EveEntityTypeEnum.choices,
    )
    eve_entity_name = models.CharField(null=False, blank=False, default="Unknown")

    objects = EveEntityManager()

    def __str__(self):
        return str(self.eve_entity_name)

    class Meta:
        verbose_name_plural = "Eve Entities"


class LoginAccessRight(models.Model):
    entity = models.ForeignKey(EveEntity, models.CASCADE)

    class Meta:
        verbose_name_plural = "Login Access Rights"


class TokenManager(models.Manager):

    def get_token(self, scope, character_id) -> Union["Token", None]:
        try:
            return self.filter(scopes__contains=scope, character_id=character_id).first()
        except Token.DoesNotExist:
            return None

    def save_sso_response(self, token_response: Dict[str, Any]):
        claims = token_response["claims"]
        character_id = claims["sub"].split(":")[-1]
        character_name = claims["name"]
        owner_hash = claims["owner"]
        scopes = claims["scp"]

        if not isinstance(claims["scp"], str):
            scopes = " ".join(claims["scp"])

        try:
            token = self.get(scopes=scopes, character_id=character_id, character_owner_hash=owner_hash)
        except Token.DoesNotExist:
            token = Token(
                scopes=scopes, character_id=character_id, character_name=character_name, character_owner_hash=owner_hash
            )
            signals.token_created.send(sender=self.__class__, token=token)

        token.access_token_backup = token_response["access_token"]
        token.refresh_token = token_response["refresh_token"]

        expires_at = datetime.datetime.fromtimestamp(claims["exp"])
        token.expires_at = timezone.make_aware(expires_at, pytz.utc)

        token.save()

    @staticmethod
    def get_jwks() -> JWKSet:
        # TODO: Change to use the REDIS cache witha Timeout
        response = requests.get("https://login.eveonline.com/.well-known/oauth-authorization-server", timeout=10)
        metadata = response.json()
        response = requests.get(metadata["jwks_uri"], timeout=10)

        jwks = JWKSet()
        jwks.import_keyset(response.text)

        return jwks

    @staticmethod
    def request_access_token_from_auth_code(authorization_code: str) -> Dict[str, Any]:
        basic_auth = base64.urlsafe_b64encode(
            f"{settings.ESI_SSO_CLIENT_ID}:{settings.ESI_SSO_CLIENT_SECRET}".encode("utf-8")
        ).decode()

        headers = {
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {"grant_type": "authorization_code", "code": authorization_code}

        response = requests.post("https://login.eveonline.com/v2/oauth/token", headers=headers, data=data)

        response.raise_for_status()

        token_response = response.json()
        jwt = JWT(jwt=token_response["access_token"], key=TokenManager.get_jwks())

        claims = json.loads(jwt.claims)
        token_response["claims"] = claims
        token_response["identity"] = {
            "character_id": claims["sub"].split(":")[-1],
            "character_name": claims["name"],
            "character_owner_hash": claims["owner"],
        }

        return token_response


class Token(models.Model):
    access_token_backup = models.TextField()
    refresh_token = models.CharField(max_length=200, blank=True, null=True)
    expires_at = models.DateTimeField()
    scopes = models.TextField(blank=True, null=True)
    character_id = models.CharField(max_length=50)
    character_name = models.CharField(max_length=255)
    character_owner_hash = models.CharField(max_length=100)

    objects = TokenManager()

    @property
    def access_token(self) -> str:
        """
        Gets the stored Access Token if valid, if expired will
        refresh the Access Token before returning

        Returns:
            str: Access Token
        """
        if timezone.now() > self.expires_at:
            self.refresh()

        return self.access_token_backup

    def refresh(self):
        """
        Refreshes the access token and updates the Token object
        """
        basic_auth = base64.urlsafe_b64encode(
            f"{settings.ESI_SSO_CLIENT_ID}:{settings.ESI_SSO_CLIENT_SECRET}".encode("utf-8")
        ).decode()

        headers = {
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}

        response = requests.post("https://login.eveonline.com/v2/oauth/token", headers=headers, data=data)

        response.raise_for_status()

        token_response = response.json()
        jwt = JWT(jwt=token_response["access_token"], key=TokenManager.get_jwks())

        claims = json.loads(jwt.claims)

        self.access_token_backup = token_response["access_token"]
        if self.refresh_token != token_response["refresh_token"]:
            self.refresh_token = token_response["refresh_token"]

        expires_at = datetime.datetime.fromtimestamp(claims["exp"])
        self.expires_at = timezone.make_aware(expires_at, pytz.utc)

        self.save()
