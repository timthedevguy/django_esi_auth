from django.contrib import admin

from .models import EveEntity, LoginAccessRight, EveUser, Token


@admin.register(EveEntity)
class EveEntityAdmin(admin.ModelAdmin):
    list_display = ["eve_entity_id", "eve_entity_name", "eve_entity_type"]
    list_filter = ["eve_entity_type"]
    search_fields = ["eve_entity_name"]


@admin.register(LoginAccessRight)
class LoginAccessRightAdmin(admin.ModelAdmin):
    list_display = ["entity", "entity__eve_entity_id", "entity__eve_entity_type"]
    list_filter = ["entity__eve_entity_type"]
    search_fields = ["entity__eve_entity_type"]


@admin.register(EveUser)
class EveUserAdmin(admin.ModelAdmin):
    list_display = [
        "username",
        "character_name",
        "character_id",
        "corporation_id",
        "alliance_id",
        "is_staff",
        "is_superuser",
        "is_active",
    ]


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ["character_id", "character_name", "character_owner", "scopes", "expires_at"]
