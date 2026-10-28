from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from audit.models import EventLog
from audit.services import log_event

from .models import User


class ProfileSerializer(serializers.ModelSerializer):
    """The logged-in user's own profile. Email and role are managed by the admin."""

    is_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "ntfy_topic",
            "role",
            "is_admin",
        ]
        read_only_fields = ["email", "role"]


class LoginSerializer(TokenObtainPairSerializer):
    """JWT login by e-mail; logs successes and failures, returns the profile."""

    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            log_event(
                EventLog.Type.USER_LOGIN_FAILED,
                actor_label=str(attrs.get(self.username_field, ""))[:150],
            )
            raise
        log_event(EventLog.Type.USER_LOGIN, actor=self.user, obj=self.user)
        data["user"] = ProfileSerializer(self.user).data
        return data


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, user=self.context["request"].user)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    """User management by the admin. Without a password, the user sets it via reset."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "ntfy_topic",
            "is_active",
            "last_login",
            "date_joined",
            "password",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def validate_password(self, value):
        validate_password(value, user=self.instance)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
