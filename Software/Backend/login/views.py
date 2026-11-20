from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from . import sesiones
from .dispositivo import LlaveDispositivo
from .models import PasswordPolicy, SesionUsuario, UserSessionSettings
from .passwords import mark_password_changed
from .permissions import es_privilegiado
from .permissions import AdministratorPermission
from .serializers import (
    DesbloqueoDispositivoSerializer,
    PasswordChangeSerializer,
    PasswordPolicySerializer,
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
        mark_password_changed(user)
        return Response({'detail': 'La contraseña fue actualizada correctamente.'})


class PasswordChangeView(APIView):
    """Cambio de contraseña con la clave actual. No exige sesión: se usa cuando la clave expiró."""
    authentication_classes = []
    permission_classes = []
    throttle_scope = 'login'

    def post(self, request, format=None):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'La contraseña fue actualizada correctamente.'})


class PasswordPolicyView(APIView):
    """Vigencia máxima global de las contraseñas (0 = sin expiración)."""
    permission_classes = [AdministratorPermission]

    def get(self, request, format=None):
        return Response(PasswordPolicySerializer(PasswordPolicy.get_solo()).data)

    def patch(self, request, format=None):
        if not es_privilegiado(request.user):
            return Response({'detail': 'Solo un Administrador Privilegiado cambia la política de contraseñas.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PasswordPolicySerializer(PasswordPolicy.get_solo(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


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
        sesiones.marcar_actividad(request.auth.get(sesiones.CLAIM_SESION) if request.auth else None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionTimeoutView(APIView):
    permission_classes = [AdministratorPermission]

    def patch(self, request, user_id, format=None):
        if not es_privilegiado(request.user):
            return Response({'detail': 'Solo un Administrador Privilegiado cambia los tiempos de sesión.'}, status=status.HTTP_403_FORBIDDEN)
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
        context = {'password_policy': PasswordPolicy.get_solo()}
        return Response(ManagedUserSerializer(users, many=True, context=context).data)

    def post(self, request, format=None):
        serializer = ManagedUserSerializer(data=request.data, context={'request': request})
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
        serializer = ManagedUserSerializer(user, data=request.data, partial=True, context={'request': request})
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
            refresh = RefreshToken(refresh_token)
            refresh.blacklist()
        except TokenError:
            return Response(
                {'detail': 'El refresh token no es válido o ya fue invalidado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sesion = SesionUsuario.objects.filter(pk=refresh.get(sesiones.CLAIM_SESION) or '').first()
        if sesion is not None:
            sesiones.cerrar(sesion, SesionUsuario.CIERRE_SALIDA)

        # App móvil: cerrar sesión también apaga el ingreso con huella en ese teléfono.
        llave = request.data.get('llave')
        if llave:
            try:
                LlaveDispositivo(llave).blacklist()
            except TokenError:
                pass  # ya vencida o canjeada: no hay nada que invalidar

        return Response(status=status.HTTP_204_NO_CONTENT)


class DesbloqueoDispositivoView(APIView):
    """POST de la app móvil tras la huella o el PIN: canjea la llave del dispositivo por una sesión."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'login'

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'  # una llave rechazada responde 401 (credencial no válida), no 403

    def post(self, request, format=None):
        serializer = DesbloqueoDispositivoSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


def _datos_sesion(sesion, actual):
    try:
        rol = get_user_role(sesion.usuario)
    except Exception:  # usuario sin rol válido: igual se muestra
        rol = None
    usuario = sesion.usuario
    return {
        'id': sesion.id,
        'usuario_id': usuario.id,
        'nombre': usuario.get_full_name() or usuario.get_username(),
        'username': usuario.get_username(),
        'rol': rol,
        'canal': sesion.canal,
        'ip': sesion.ip,
        'dispositivo': sesion.dispositivo,
        'inicio': sesion.inicio,
        'ultima_actividad': sesion.ultima_actividad,
        'actual': sesion.id == actual,
    }


class SesionesActivasView(APIView):
    """GET (Administrador y Administrador Privilegiado): sesiones abiertas y en uso."""

    permission_classes = [AdministratorPermission]

    def get(self, request, format=None):
        actual = request.auth.get(sesiones.CLAIM_SESION) if request.auth else None
        return Response([_datos_sesion(s, actual) for s in sesiones.activas()])


class RevocarSesionesView(APIView):
    """POST {"sesion": id} o {"usuario": id}: cierra una sesión o todas las de un usuario, al instante."""

    permission_classes = [AdministratorPermission]

    def post(self, request, format=None):
        actual = request.auth.get(sesiones.CLAIM_SESION) if request.auth else None
        sesion_id = request.data.get('sesion')
        usuario_id = request.data.get('usuario')
        abiertas = SesionUsuario.objects.filter(cerrada_en__isnull=True)
        if sesion_id:
            if sesion_id == actual:
                return Response({'detail': 'Esta es tu sesión actual: para cerrarla usa "Salir".'},
                                status=status.HTTP_400_BAD_REQUEST)
            objetivo = abiertas.filter(pk=sesion_id)
            if not objetivo.exists():
                return Response({'detail': 'La sesión no existe o ya está cerrada.'}, status=status.HTTP_404_NOT_FOUND)
        elif str(usuario_id or '').isdigit():
            objetivo = abiertas.filter(usuario_id=int(usuario_id)).exclude(pk=actual or '')
        else:
            return Response({'detail': 'Indica la sesión o el usuario.'}, status=status.HTTP_400_BAD_REQUEST)
        revocadas = 0
        for sesion in objetivo:
            sesiones.cerrar(sesion, SesionUsuario.CIERRE_REVOCADA)
            revocadas += 1
        return Response({'revocadas': revocadas})
