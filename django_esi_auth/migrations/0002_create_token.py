from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buyback", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Token",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("access_token_backup", models.TextField()),
                ("refresh_token", models.CharField(blank=True, max_length=200, null=True)),
                ("expires_at", models.DateTimeField()),
                ("scopes", models.TextField(blank=True, null=True)),
                ("character_id", models.CharField(max_length=50)),
                ("character_name", models.CharField(max_length=255)),
                ("character_owner_hash", models.CharField(max_length=100)),
            ],
        ),
    ]
