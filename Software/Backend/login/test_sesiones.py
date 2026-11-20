"""Sesiones activas: registro al iniciar sesión, listado para administradores y revocación inmediata."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import SesionUsuario
from .serializers import EmailTokenObtainPairSerializer

CLAVE = 'Clave-de-prueba-123!'
CHROME_WINDOWS = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
APP_ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36'


class SesionesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = self.usuario('admin', 'Administrador')
        self.tecnico = self.usuario('tecnico', 'Tecnico')

    def usuario(self, nombre, grupo):
        u = get_user_model().objects.create_user(username=nombre, password=CLAVE, first_name=nombre.title())
        u.groups.set([Group.objects.get_or_create(name=grupo)[0]])
        return u

    def login(self, nombre, canal='web', agente=CHROME_WINDOWS, **extra):
        cache.clear()
        r = APIClient().post('/api/auth/token/', {'username': nombre, 'password': CLAVE, 'canal': canal},
                             format='json', HTTP_USER_AGENT=agente, **extra)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def cliente(self, tokens):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return c

    def test_el_login_registra_la_sesion_con_canal_ip_y_dispositivo(self):
        # Detrás del túnel la IP real viene en CF-Connecting-IP.
        self.login('tecnico', REMOTE_ADDR='127.0.0.1', HTTP_CF_CONNECTING_IP='200.1.2.3')
        sesion = SesionUsuario.objects.get(usuario=self.tecnico)
        self.assertEqual((sesion.canal, sesion.ip, sesion.dispositivo), ('web', '200.1.2.3', 'Chrome · Windows'))

    def test_la_app_movil_queda_identificada(self):
        self.login('tecnico', canal='movil', agente=APP_ANDROID)
        sesion = SesionUsuario.objects.get(usuario=self.tecnico)
        self.assertEqual((sesion.canal, sesion.dispositivo), ('movil', 'App SICMA · Android'))

    def test_el_administrador_ve_las_sesiones_y_cual_es_la_suya(self):
        self.login('tecnico')
        admin = self.login('admin')
        lista = self.cliente(admin).get('/api/auth/sesiones/').json()
        self.assertEqual({s['username']: s['actual'] for s in lista}, {'tecnico': False, 'admin': True})
        tecnico = next(s for s in lista if s['username'] == 'tecnico')
        self.assertEqual((tecnico['rol'], tecnico['canal']), ('tecnico', 'web'))

    def test_revocar_corta_la_sesion_al_instante_y_no_se_puede_renovar(self):
        tecnico = self.login('tecnico')
        self.assertEqual(self.cliente(tecnico).get('/api/auth/me/').status_code, 200)
        admin = self.login('admin')
        sesion = SesionUsuario.objects.get(usuario=self.tecnico)
        r = self.cliente(admin).post('/api/auth/sesiones/revocar/', {'sesion': sesion.id}, format='json')
        self.assertEqual(r.json(), {'revocadas': 1})

        # El access token sigue vigente por tiempo, pero la API lo rechaza en la siguiente petición.
        r = self.cliente(tecnico).get('/api/auth/me/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['code'], 'sesion_revocada')
        r = APIClient().post('/api/auth/token/refresh/', {'refresh': tecnico['refresh']}, format='json')
        self.assertEqual(r.status_code, 401)
        # Y deja de aparecer en la lista.
        self.assertNotIn('tecnico', [s['username'] for s in self.cliente(admin).get('/api/auth/sesiones/').json()])

    def test_revocar_la_sesion_de_la_app_apaga_su_huella(self):
        movil = self.login('tecnico', canal='movil', agente=APP_ANDROID)
        admin = self.login('admin')
        sesion = SesionUsuario.objects.get(usuario=self.tecnico)
        self.cliente(admin).post('/api/auth/sesiones/revocar/', {'sesion': sesion.id}, format='json')
        cache.clear()
        r = APIClient().post('/api/auth/token/dispositivo/', {'llave': movil['llave']}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_revocar_todas_las_de_un_usuario(self):
        primera, segunda = self.login('tecnico'), self.login('tecnico', canal='movil', agente=APP_ANDROID)
        admin = self.login('admin')
        r = self.cliente(admin).post('/api/auth/sesiones/revocar/', {'usuario': self.tecnico.id}, format='json')
        self.assertEqual(r.json(), {'revocadas': 2})
        self.assertEqual(self.cliente(primera).get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.cliente(segunda).get('/api/auth/me/').status_code, 401)

    def test_no_puede_revocar_su_propia_sesion_actual(self):
        admin = self.login('admin')
        propia = SesionUsuario.objects.get(usuario=self.admin)
        r = self.cliente(admin).post('/api/auth/sesiones/revocar/', {'sesion': propia.id}, format='json')
        self.assertEqual(r.status_code, 400)
        # Al revocar "todas las suyas" se salta la actual.
        r = self.cliente(admin).post('/api/auth/sesiones/revocar/', {'usuario': self.admin.id}, format='json')
        self.assertEqual(r.json(), {'revocadas': 0})
        self.assertEqual(self.cliente(admin).get('/api/auth/me/').status_code, 200)

    def test_cerrar_sesion_la_saca_de_la_lista_sin_marcarla_revocada(self):
        tecnico = self.login('tecnico')
        r = self.cliente(tecnico).post('/api/auth/logout/', {'refresh': tecnico['refresh']}, format='json')
        self.assertEqual(r.status_code, 204)
        sesion = SesionUsuario.objects.get(usuario=self.tecnico)
        self.assertEqual(sesion.motivo_cierre, SesionUsuario.CIERRE_SALIDA)
        admin = self.login('admin')
        self.assertNotIn('tecnico', [s['username'] for s in self.cliente(admin).get('/api/auth/sesiones/').json()])

    def test_la_actividad_se_registra_por_sesion_y_la_inactiva_no_se_lista(self):
        tecnico = self.login('tecnico')
        sesion = SesionUsuario.objects.get(usuario=self.tecnico)
        SesionUsuario.objects.filter(pk=sesion.pk).update(ultima_actividad=timezone.now() - timedelta(hours=1))
        admin = self.login('admin')
        self.assertNotIn('tecnico', [s['username'] for s in self.cliente(admin).get('/api/auth/sesiones/').json()])
        # La persona vuelve a usar la página: la sesión vuelve a contar como activa.
        self.assertEqual(self.cliente(tecnico).post('/api/auth/activity/', {}, format='json').status_code, 204)
        self.assertIn('tecnico', [s['username'] for s in self.cliente(admin).get('/api/auth/sesiones/').json()])

    def test_los_tokens_emitidos_antes_del_registro_siguen_funcionando(self):
        # Tokens sin fila de sesión (p. ej. emitidos antes de desplegar esta función).
        token = EmailTokenObtainPairSerializer.get_token(self.tecnico).access_token
        self.assertEqual(self.cliente({'access': str(token)}).get('/api/auth/me/').status_code, 200)

    def test_otros_roles_no_ven_ni_revocan(self):
        tecnico = self.login('tecnico')
        self.assertEqual(self.cliente(tecnico).get('/api/auth/sesiones/').status_code, 403)
        self.assertEqual(self.cliente(tecnico).post('/api/auth/sesiones/revocar/', {'usuario': self.admin.id},
                                                     format='json').status_code, 403)
