from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from rest_framework import serializers

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        try:
            password_validation.validate_password(value)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value
