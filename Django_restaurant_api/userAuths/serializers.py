from rest_framework import serializers
from .models import TelegramUser

class TelegramUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramUser
        fields = "__all__"

        # IMPORTANT:
        # telegram_id has unique=True at the DB level, so DRF auto-adds a UniqueValidator.
        # That validator rejects existing IDs BEFORE update_or_create() runs,
        # breaking idempotent "create-or-update" behavior.
        # We disable serializer-level uniqueness here and let the DB + business logic handle update_or_create() safely.
        # that why we disbled validators by setting it to an empty list = []
        extra_kwargs = {
            'telegram_id': {'validators': []},  # 🔥 disables unique check
        }



# Invoke-RestMethod -Uri http://127.0.0.1:8000/userauths/register_user/ `
#   -Method POST `
#   -ContentType "application/json" `
#   -Body '{"telegram_id":5680916028,"first_name":"Baddest guy","username":"Danshanu55"}'

# Invoke-RestMethod -Uri http://127.0.0.1:8000/api/update_batch_status/UkWNeewkMe/`
#   -Method GET `
#   -ContentType "application/json" `
#   -Body '{"telegram_id":5680916028,"status":"processing", "batch_id":"AyRtNTEDAK"}'











