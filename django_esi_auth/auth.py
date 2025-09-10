import hashlib
import json
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import AbstractBaseUser, Group
from django.http import HttpRequest
from django.utils import timezone

from .choices import EveEntityTypeEnum
from .models import LoginAccessRight, EveUser


class EveAuthenticationBackend(BaseBackend):
    """Authentication backend that uses django-esi and Eve Online SSO to
    authenticate Django users.

    Users are created with username that populates from a hash generated using
    Character ID and Character Owner Hash of the character.  Should ensure a new
    user if the account gets transfered.
    ```
    username = hashlib.md5(f'{character_id}.{character_owner_hash}'.encode()).hexdigest().upper()
    ```
    """

    def authenticate(self, request: HttpRequest, **kwargs) -> AbstractBaseUser | None:
        user = None
        is_admin = False

        if "password" not in kwargs:
            if EveUser.objects.all().count() == 0:
                is_admin = True

            if "token_response" in kwargs:
                token_response = kwargs["token_response"]

                if token_response:
                    if token_response["identity"]["character_owner_hash"]:
                        owner = (
                            hashlib.md5(
                                f"{token_response['identity']['character_id']}.{token_response['identity']['character_owner_hash']}".encode()
                            )
                            .hexdigest()
                            .upper()
                        )
                        try:
                            user = EveUser.objects.get(username=owner)
                        except EveUser.DoesNotExist:
                            user = EveUser(
                                username=owner,
                                is_superuser=is_admin,
                                is_staff=is_admin,
                                character_id=token_response["identity"]["character_id"],
                                character_owner_hash=token_response["identity"]["character_owner_hash"],
                                character_name=token_response["identity"]["character_name"],
                            )
                            user.first_name = token_response["identity"]["character_name"].split(" ")[0]
                            user.last_name = token_response["identity"]["character_name"].split(" ")[-1]
                            user.save()

                            if settings.DJANGO_ESI_AUTH_DEFAULT_GROUP:
                                group = Group.objects.get(name=settings.DJANGO_ESI_AUTH_DEFAULT_GROUP)
                                user.groups.add(group)
                                user.save()

            if self.has_login_rights(user):
                return user

        return None

    def get_user(self, user_id):
        try:
            return EveUser.objects.get(pk=user_id)
        except EveUser.DoesNotExist:
            return None

    def has_login_rights(self, user: EveUser) -> bool:

        if user.is_superuser:
            return True

        if user.last_access_check is None or user.last_access_check < timezone.now() - timedelta(days=1):
            public_data = self.get_public_character_data(user.character_id)
            user.corporation_id = public_data.get("corporation_id", None)
            user.alliance_id = public_data.get("alliance_id", None)
            user.last_access_check = timezone.now()
            user.save()

        if (
            LoginAccessRight.objects.filter(
                entity__eve_entity_id=user.character_id,
                entity__eve_entity_type=EveEntityTypeEnum.CHARACTER,
            ).exists()
            or LoginAccessRight.objects.filter(
                entity__eve_entity_id=user.alliance_id,
                entity__eve_entity_type=EveEntityTypeEnum.ALLIANCE,
            ).exists()
            or LoginAccessRight.objects.filter(
                entity__eve_entity_id=user.corporation_id,
                entity__eve_entity_type=EveEntityTypeEnum.CORPORATION,
            ).exists()
        ):
            return True

        return False

    def get_public_character_data(self, character_id):
        response = requests.get(
            f"https://esi.evetech.net/latest/characters/{character_id}/?datasource=tranquility",
            timeout=10,
        )

        if response:
            return json.loads(response.text)

        return None
