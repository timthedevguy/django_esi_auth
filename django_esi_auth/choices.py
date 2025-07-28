from django.db import models


class EveEntityTypeEnum(models.TextChoices):
    CHARACTER = "character", "Character"
    CORPORATION = "corporation", "Corporation"
    ALLIANCE = "alliance", "Alliance"
    STATION = "station", "Station"
    STRUCTURE = "structure", "Structure"
    UNKNOWN = "unknown", "Unknown"
