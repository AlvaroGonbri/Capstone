from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import EmailTokenObtainPairSerializer
from .views import (
    ExampleView,
    PasswordChangeView,
    PasswordPolicyView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    LogoutView,
    SessionTimeoutView,
    ManagedUserListView,
    ManagedUserDetailView,
    ActivityView,
    DesbloqueoDispositivoView,
    InactivityAwareTokenRefreshView,
    RevocarSesionesView,
    SesionesActivasView,
)


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = 'login'

urlpatterns = [
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', InactivityAwareTokenRefreshView.as_view(), name='token_refresh'),
    # App móvil: entrar con huella o PIN del teléfono (canjea la llave del dispositivo).
    path('token/dispositivo/', DesbloqueoDispositivoView.as_view(), name='token_dispositivo'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-change/', PasswordChangeView.as_view(), name='password_change'),
    path('password-policy/', PasswordPolicyView.as_view(), name='password_policy'),
    path('me/', ExampleView.as_view(), name='current_user'),
    path('activity/', ActivityView.as_view(), name='activity'),
    path('users/<int:user_id>/session-timeout/', SessionTimeoutView.as_view(), name='user_session_timeout'),
    path('users/', ManagedUserListView.as_view(), name='managed_user_list'),
    path('users/<int:user_id>/', ManagedUserDetailView.as_view(), name='managed_user_detail'),
    path('logout/', LogoutView.as_view(), name='logout'),
    # Sesiones activas: las ven y revocan el Administrador y el Administrador Privilegiado.
    path('sesiones/', SesionesActivasView.as_view(), name='sesiones_lista'),
    path('sesiones/revocar/', RevocarSesionesView.as_view(), name='sesiones_revocar'),
]