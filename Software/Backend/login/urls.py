from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import EmailTokenObtainPairSerializer
from .views import (
    ExampleView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    LogoutView,
    SessionTimeoutView,
    ManagedUserListView,
    ManagedUserDetailView,
    ActivityView,
    InactivityAwareTokenRefreshView,
)


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = 'login'

urlpatterns = [
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', InactivityAwareTokenRefreshView.as_view(), name='token_refresh'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('me/', ExampleView.as_view(), name='current_user'),
    path('activity/', ActivityView.as_view(), name='activity'),
    path('users/<int:user_id>/session-timeout/', SessionTimeoutView.as_view(), name='user_session_timeout'),
    path('users/', ManagedUserListView.as_view(), name='managed_user_list'),
    path('users/<int:user_id>/', ManagedUserDetailView.as_view(), name='managed_user_detail'),
    path('logout/', LogoutView.as_view(), name='logout'),
]