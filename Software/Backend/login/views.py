from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from .models import UserSessionSettings
from .permissions import AdministratorPermission
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ManagedUserSerializer,
    InactivityAwareTokenRefreshSerializer,
    SessionTimeoutSerializer,
    get_inactivity_timeout_minutes,
    get_user_role,
)


User = get_user_model()


class InactivityAwareTokenRefreshView(TokenRefreshView):
    serializer_class = InactivityAwareTokenRefreshSerializer


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_scope = 'password_reset'

    def post(self, request, format=None):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(
            email__iexact=serializer.validated_data['email'],
            is_active=True,
        ).first()

        if user and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = (
                f'{settings.PASSWORD_RESET_CONFIRM_URL}'
                f'?uid={uid}&token={token}'
            )
            send_mail(
                subject='Recuperación de contraseña',
                message=(
                    'Usa el siguiente enlace para restablecer tu contraseña:\n\n'
                    f'{reset_url}\n\n'
                    'Si no solicitaste este cambio, ignora este mensaje.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        return Response(
            {'detail': 'Si el correo existe, recibirás instrucciones para restablecer tu contraseña.'},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, format=None):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = request.data.get('uid') or request.query_params.get('uid', '')
        token = request.data.get('token') or request.query_params.get('token', '')

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'detail': 'El enlace de recuperación no es válido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {'detail': 'El enlace de recuperación no es válido o ha expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])
        return Response({'detail': 'La contraseña fue actualizada correctamente.'})

class ExampleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        content = {
            'id': user.id,
            'username': user.get_username(),
            'email': user.email,
            'nombre': user.get_full_name() or user.get_username(),
            'rol': get_user_role(user),
            'inactivity_timeout_minutes': get_inactivity_timeout_minutes(user),
        }
        return Response(content)


class ActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        settings, _ = UserSessionSettings.objects.get_or_create(user=request.user)
        settings.last_activity_at = timezone.now()
        settings.save(update_fields=['last_activity_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionTimeoutView(APIView):
    permission_classes = [AdministratorPermission]

    def patch(self, request, user_id, format=None):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response(
                {'detail': 'El usuario no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        settings, _ = UserSessionSettings.objects.get_or_create(user=user)
        serializer = SessionTimeoutSerializer(
            settings,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ManagedUserListView(APIView):
    permission_classes = [AdministratorPermission]

    def _is_admin(self, request):
        return request.user.groups.filter(
            name__in=('Administrador', 'AdministradorPrivilegiado'),
        ).exists()

    def get(self, request, format=None):
        users = User.objects.select_related('session_settings').prefetch_related('groups').order_by('id')
        return Response(ManagedUserSerializer(users, many=True).data)

    def post(self, request, format=None):
        serializer = ManagedUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(ManagedUserSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


class ManagedUserDetailView(APIView):
    permission_classes = [AdministratorPermission]

    def _is_admin(self, request):
        return request.user.groups.filter(
            name__in=('Administrador', 'AdministradorPrivilegiado'),
        ).exists()

    def patch(self, request, user_id, format=None):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response({'detail': 'El usuario no existe.'}, status=404)
        serializer = ManagedUserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(ManagedUserSerializer(serializer.save()).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Debe enviar el refresh token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {'detail': 'El refresh token no es válido o ya fue invalidado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
