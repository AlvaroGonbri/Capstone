"""Ingreso con huella o PIN en la app móvil: la llave del dispositivo (login/dispositivo.py)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .dispositivo import LlaveDispositivo, emitir_llave
from .models import UserSessionSettings

CLAVE = 'Clave-de-prueba-123!'


class LlaveDispositivoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = get_user_model().objects.create_user(username='movil', email='movil@test.cl', password=CLAVE)
        self.usuario.groups.set([Group.objects.get_or_create(name='Administrador')[0]])
        self.cliente = APIClient()

    def login(self, canal):
        r = self.cliente.post('/api/auth/token/', {'username': 'movil', 'password': CLAVE, 'canal': canal}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def canjear(self, llave):
        cache.clear()
        return self.cliente.post('/api/auth/token/dispositivo/', {'llave': llave}, format='json')

    def test_solo_la_app_movil_recibe_la_llave(self):
        self.assertIn('llave', self.login('movil'))
        self.assertNotIn('llave', self.login('web'))

    def test_canje_entrega_sesion_de_solo_lectura_y_una_llave_nueva_con_el_mismo_vencimiento(self):
        llave = self.login('movil')['llave']
        r = self.canjear(llave)
        self.assertEqual(r.status_code, 200, r.content)
        datos = r.json()
        self.assertTrue(AccessToken(datos['access'])['solo_lectura'])
        self.assertNotEqual(datos['llave'], llave)
        self.assertEqual(LlaveDispositivo(datos['llave'])['exp'], LlaveDispositivo(llave, verify=False)['exp'])

        # La sesión obtenida no puede modificar nada.
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {datos['access']}")
        self.assertEqual(api.post('/api/activos/', {}, format='json').status_code, 403)

    def test_la_llave_es_de_un_solo_uso(self):
        llave = self.login('movil')['llave']
        self.assertEqual(self.canjear(llave).status_code, 200)
        self.assertEqual(self.canjear(llave).status_code, 401)

    def test_desbloquea_aunque_la_sesion_haya_expirado_por_inactividad(self):
        llave = self.login('movil')['llave']
        UserSessionSettings.objects.filter(user=self.usuario).update(
            last_activity_at=timezone.now() - timedelta(hours=5),
        )
        self.assertEqual(self.canjear(llave).status_code, 200)

    def test_la_llave_vencida_no_sirve(self):
        vencida = emitir_llave(self.usuario, vence=int((timezone.now() - timedelta(minutes=1)).timestamp()))
        self.assertEqual(self.canjear(str(vencida)).status_code, 401)

    def test_vence_a_los_7_dias(self):
        llave = LlaveDispositivo(self.login('movil')['llave'])
        dias = (llave['exp'] - timezone.now().timestamp()) / 86400
        self.assertAlmostEqual(dias, 7, places=2)

    def test_cambiar_la_contrasena_invalida_la_llave(self):
        llave = self.login('movil')['llave']
        self.usuario.set_password('Otra-clave-distinta-456!')
        self.usuario.save()
        self.assertEqual(self.canjear(llave).status_code, 401)

    def test_cuenta_desactivada_no_entra(self):
        llave = self.login('movil')['llave']
        self.usuario.is_active = False
        self.usuario.save()
        self.assertEqual(self.canjear(llave).status_code, 401)

    def test_cerrar_sesion_invalida_la_llave(self):
        datos = self.login('movil')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {datos['access']}")
        r = api.post('/api/auth/logout/', {'refresh': datos['refresh'], 'llave': datos['llave']}, format='json')
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.canjear(datos['llave']).status_code, 401)

    def test_la_llave_no_sirve_fuera_de_su_ruta(self):
        datos = self.login('movil')
        # Ni como refresh token normal...
        r = self.cliente.post('/api/auth/token/refresh/', {'refresh': datos['llave']}, format='json')
        self.assertEqual(r.status_code, 401)
        # ...ni para llamar a la API...
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {datos['llave']}")
        self.assertEqual(api.get('/api/activos/').status_code, 401)
        # ...y un refresh token normal no sirve como llave.
        self.assertEqual(self.canjear(datos['refresh']).status_code, 401)
