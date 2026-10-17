from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import PasswordPolicy, UserSessionSettings


User = get_user_model()
CLAVE = 'Clave-Segura-2026'
SIN_THROTTLE = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
}


def crear_usuario(username, rol='Tecnico', **extra):
    usuario = User.objects.create_user(username=username, email=f'{username}@sicma.test', password=CLAVE)
    usuario.groups.set([Group.objects.get_or_create(name=rol)[0]])
    UserSessionSettings.objects.create(user=usuario, **extra)
    return usuario


@override_settings(REST_FRAMEWORK=SIN_THROTTLE)
class VencimientoContrasenaTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        PasswordPolicy.objects.update_or_create(pk=1, defaults={'max_age_days': 30})
        hace_40_dias = timezone.now() - timedelta(days=40)
        self.vencido = crear_usuario('vencido', password_changed_at=hace_40_dias)
        self.exento = crear_usuario('exento', password_changed_at=hace_40_dias, password_never_expires=True)

    def login(self, username, password=CLAVE):
        return self.cliente.post('/api/auth/token/', {'username': username, 'password': password}, format='json')

    def test_login_con_contrasena_vencida_responde_password_expired(self):
        respuesta = self.login('vencido@sicma.test')
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()['code'], 'password_expired')

    def test_clave_incorrecta_no_revela_que_la_cuenta_esta_vencida(self):
        respuesta = self.login('vencido', 'otra-clave')
        self.assertEqual(respuesta.status_code, 401)
        self.assertNotIn('password_expired', respuesta.content.decode())

    def test_cuenta_que_nunca_expira_puede_ingresar(self):
        self.assertEqual(self.login('exento').status_code, 200)

    def test_politica_en_cero_desactiva_el_vencimiento(self):
        PasswordPolicy.objects.filter(pk=1).update(max_age_days=0)
        self.assertEqual(self.login('vencido').status_code, 200)

    def test_cambiar_contrasena_vencida_permite_volver_a_ingresar(self):
        respuesta = self.cliente.post('/api/auth/password-change/', {
            'username': 'vencido@sicma.test',
            'current_password': CLAVE,
            'new_password': 'Nueva-Clave-2026!',
        }, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.login('vencido', 'Nueva-Clave-2026!').status_code, 200)

    def test_cambio_rechaza_clave_actual_incorrecta_y_clave_repetida(self):
        url = '/api/auth/password-change/'
        mala = self.cliente.post(url, {'username': 'vencido', 'current_password': 'x', 'new_password': 'Nueva-Clave-2026!'}, format='json')
        repetida = self.cliente.post(url, {'username': 'vencido', 'current_password': CLAVE, 'new_password': CLAVE}, format='json')
        self.assertEqual(mala.status_code, 400)
        self.assertEqual(repetida.status_code, 400)
        self.assertIn('new_password', repetida.json())

    def test_refresh_falla_si_la_contrasena_vence_durante_la_sesion(self):
        PasswordPolicy.objects.filter(pk=1).update(max_age_days=0)
        refresh = self.login('vencido').json()['refresh']
        PasswordPolicy.objects.filter(pk=1).update(max_age_days=30)
        respuesta = self.cliente.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()['code'], 'password_expired')


@override_settings(REST_FRAMEWORK=SIN_THROTTLE)
class AdministracionVencimientoTests(TestCase):
    def setUp(self):
        self.cliente = APIClient()
        self.admin = crear_usuario('admin', rol='AdministradorPrivilegiado')
        self.tecnico = crear_usuario('tecnico')

    def test_administrador_cambia_la_vigencia_global(self):
        self.cliente.force_authenticate(self.admin)
        respuesta = self.cliente.patch('/api/auth/password-policy/', {'max_age_days': 45}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(PasswordPolicy.get_solo().max_age_days, 45)

    def test_vigencia_fuera_de_rango_se_rechaza(self):
        self.cliente.force_authenticate(self.admin)
        respuesta = self.cliente.patch('/api/auth/password-policy/', {'max_age_days': 400}, format='json')
        self.assertEqual(respuesta.status_code, 400)

    def test_tecnico_no_puede_ver_ni_cambiar_la_politica(self):
        self.cliente.force_authenticate(self.tecnico)
        self.assertEqual(self.cliente.get('/api/auth/password-policy/').status_code, 403)
        self.assertEqual(self.cliente.patch('/api/auth/password-policy/', {'max_age_days': 0}, format='json').status_code, 403)

    def test_administrador_marca_una_cuenta_sin_expiracion(self):
        self.cliente.force_authenticate(self.admin)
        respuesta = self.cliente.patch(f'/api/auth/users/{self.tecnico.id}/', {'password_never_expires': True}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['password_never_expires'])
        self.assertIsNone(respuesta.json()['password_expires_at'])
        self.assertTrue(UserSessionSettings.objects.get(user=self.tecnico).password_never_expires)

    def test_lista_de_usuarios_informa_el_vencimiento(self):
        self.cliente.force_authenticate(self.admin)
        fila = next(u for u in self.cliente.get('/api/auth/users/').json() if u['id'] == self.tecnico.id)
        self.assertFalse(fila['password_expired'])
        self.assertIsNotNone(fila['password_expires_at'])


class PermisosPorRolTests(TestCase):
    def test_usuario_sin_rol_no_consulta_infraestructura_ni_mediciones(self):
        cliente = APIClient()
        cliente.force_authenticate(User.objects.create_user(username='sinrol', password=CLAVE))
        self.assertEqual(cliente.get('/api/infraestructura/activos/').status_code, 403)
        self.assertEqual(cliente.get('/api/mediciones/').status_code, 403)
