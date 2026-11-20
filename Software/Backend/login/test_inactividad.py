"""Cierre de sesión por inactividad (RNF-SEG): renovar el token no debe contar como actividad.

La app consulta el servidor sola cada pocos segundos (alertas, estado) y, cuando vence el token de
acceso (5 min), lo renueva sin que la persona haga nada. Si la renovación contara como actividad, la
sesión nunca expiraría.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import UserSessionSettings

CLAVE = 'Clave-de-prueba-123!'


class InactividadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = get_user_model().objects.create_user(username='inactivo', password=CLAVE)
        self.usuario.groups.set([Group.objects.get_or_create(name='Tecnico')[0]])
        r = APIClient().post('/api/auth/token/', {'username': 'inactivo', 'password': CLAVE}, format='json')
        self.tokens = r.json()
        self.ajustes = UserSessionSettings.objects.get(user=self.usuario)  # tiempo por defecto: 15 min

    def sin_actividad_desde(self, minutos):
        self.ajustes.last_activity_at = timezone.now() - timedelta(minutes=minutos)
        self.ajustes.save(update_fields=['last_activity_at'])

    def renovar(self):
        return APIClient().post('/api/auth/token/refresh/', {'refresh': self.tokens['refresh']}, format='json')

    def test_renovar_no_reinicia_el_contador(self):
        self.sin_actividad_desde(10)
        antes = UserSessionSettings.objects.get(user=self.usuario).last_activity_at
        self.assertEqual(self.renovar().status_code, 200)
        self.assertEqual(UserSessionSettings.objects.get(user=self.usuario).last_activity_at, antes)

    def test_renovaciones_automaticas_no_mantienen_viva_la_sesion(self):
        ahora = timezone.now()
        # Minuto 10 sin tocar nada: la consulta periódica renueva el token (todavía dentro del plazo).
        self.sin_actividad_desde(10)
        self.assertEqual(self.renovar().status_code, 200)
        # Pasan 6 minutos más (minuto 16), sin actividad real entremedio: se venció el plazo de 15.
        with patch('login.serializers.timezone.now', return_value=ahora + timedelta(minutes=6)):
            respuesta = self.renovar()
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn('inactividad', respuesta.json()['detail'])

    def test_la_actividad_real_si_mantiene_la_sesion(self):
        self.sin_actividad_desde(14)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}")
        # La persona toca la pantalla: la app avisa la actividad y el contador vuelve a cero.
        self.assertIn(api.post('/api/auth/activity/', {}, format='json').status_code, (200, 204))
        ajustes = UserSessionSettings.objects.get(user=self.usuario)
        self.assertLess(timezone.now() - ajustes.last_activity_at, timedelta(seconds=5))
        self.assertEqual(self.renovar().status_code, 200)
