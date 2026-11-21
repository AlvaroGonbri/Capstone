"""Verificación en dos pasos (TOTP): configuración, ingreso, respaldo, bloqueo y administración."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from . import mfa
from .models import SesionUsuario, UserSessionSettings

CLAVE = 'Clave-de-prueba-123!'


class VerificacionDosPasosTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tecnico = self.usuario('tecnico', 'Tecnico')
        self.priv = self.usuario('priv', 'AdministradorPrivilegiado')
        self.admin = self.usuario('admin', 'Administrador')

    def usuario(self, nombre, grupo):
        u = get_user_model().objects.create_user(username=nombre, email=f'{nombre}@test.cl', password=CLAVE)
        u.groups.set([Group.objects.get_or_create(name=grupo)[0]])
        return u

    def login(self, nombre='tecnico', canal='web', clave=CLAVE):
        cache.clear()
        return APIClient().post('/api/auth/token/', {'username': nombre, 'password': clave, 'canal': canal}, format='json')

    def codigo(self, mfa_token, codigo):
        cache.clear()
        return APIClient().post('/api/auth/token/mfa/', {'mfa_token': mfa_token, 'codigo': codigo}, format='json')

    def accion(self, accion, quien=None, usuario=None):
        datos = self.login(quien or 'priv').json()
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {datos['access']}")
        return api.post(f'/api/auth/users/{(usuario or self.tecnico).id}/mfa/', {'accion': accion}, format='json')

    def ajustes(self):
        return UserSessionSettings.objects.get_or_create(user=self.tecnico)[0]

    def configurar(self):
        """Exige la verificación al técnico y la configura; devuelve los códigos de respaldo."""
        self.accion('exigir')
        desafio = self.login().json()
        r = self.codigo(desafio['mfa_token'], mfa.codigo_actual(desafio['secreto']))
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['codigos_respaldo']

    # ------------------------------------------------------------------ TOTP

    def test_totp_coincide_con_el_vector_del_rfc_6238(self):
        # RFC 6238, apéndice B: secreto ASCII "12345678901234567890", t = 59 -> 94287082 (8 dígitos).
        secreto = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
        self.assertEqual(mfa._hotp(secreto, 59 // 30), '287082')  # los 6 últimos dígitos

    def test_sin_exigencia_el_login_no_cambia(self):
        datos = self.login().json()
        self.assertIn('access', datos)
        self.assertNotIn('mfa', datos)

    # ------------------------------------------------------------------ configuración

    def test_la_primera_vez_entrega_el_qr_y_al_confirmar_los_codigos_de_respaldo(self):
        self.assertEqual(self.accion('exigir').json(), {'mfa': 'pendiente'})
        desafio = self.login().json()
        self.assertEqual(desafio['mfa'], 'configurar')
        self.assertNotIn('access', desafio)  # sin el código no hay sesión
        self.assertTrue(desafio['qr'].startswith('data:image/svg+xml;base64,'))

        r = self.codigo(desafio['mfa_token'], mfa.codigo_actual(desafio['secreto']))
        datos = r.json()
        self.assertIn('access', datos)
        self.assertEqual(len(datos['codigos_respaldo']), mfa.CODIGOS_RESPALDO)
        self.assertTrue(self.ajustes().mfa_activa)
        self.assertTrue(SesionUsuario.objects.filter(usuario=self.tecnico).exists())

    def test_si_abandona_la_configuracion_se_conserva_el_mismo_secreto(self):
        self.accion('exigir')
        primero = self.login().json()['secreto']
        self.assertEqual(self.login().json()['secreto'], primero)

    # ------------------------------------------------------------------ ingreso

    def test_ingreso_con_codigo_y_rechazo_de_codigo_incorrecto(self):
        self.configurar()
        desafio = self.login().json()
        self.assertEqual(desafio['mfa'], 'codigo')
        self.assertNotIn('secreto', desafio)  # el secreto solo se entrega al configurar
        r = self.codigo(desafio['mfa_token'], '000000')
        self.assertEqual((r.status_code, r.json()['code']), (401, 'mfa_incorrecto'))
        # Un código del intervalo siguiente (reloj del teléfono adelantado) sí sirve.
        import time
        siguiente = mfa._hotp(self.ajustes().mfa_secreto, int(time.time() // 30) + 1)
        self.assertEqual(self.codigo(desafio['mfa_token'], siguiente).status_code, 200)

    def test_un_codigo_no_sirve_dos_veces(self):
        self.configurar()  # usó el código del intervalo actual
        desafio = self.login().json()
        r = self.codigo(desafio['mfa_token'], mfa.codigo_actual(self.ajustes().mfa_secreto))
        self.assertEqual(r.status_code, 401)

    def test_codigo_de_respaldo_sirve_una_sola_vez(self):
        respaldo = self.configurar()[0]
        self.assertEqual(self.codigo(self.login().json()['mfa_token'], respaldo.upper()).status_code, 200)
        self.assertEqual(self.codigo(self.login().json()['mfa_token'], respaldo).status_code, 401)
        self.assertEqual(len(self.ajustes().mfa_codigos_respaldo), mfa.CODIGOS_RESPALDO - 1)

    def test_codigos_erroneos_bloquean_la_cuenta_aunque_la_contrasena_sea_correcta(self):
        self.configurar()
        for _ in range(5):  # LOGIN_MAX_INTENTOS: el login con contraseña no reinicia el contador
            self.codigo(self.login().json()['mfa_token'], '000000')
        r = self.login()
        self.assertEqual((r.status_code, r.json()['code']), (403, 'account_locked'))

    def test_el_paso_intermedio_vence_y_no_se_puede_alterar(self):
        self.configurar()
        desafio = self.login().json()
        self.assertEqual(self.codigo(desafio['mfa_token'] + 'x', '123456').json()['code'], 'mfa_vencido')
        with patch.object(mfa, 'VIGENCIA_DESAFIO_SEGUNDOS', -1):
            r = self.codigo(desafio['mfa_token'], mfa.codigo_actual(self.ajustes().mfa_secreto))
        self.assertEqual(r.json()['code'], 'mfa_vencido')

    def test_cambiar_la_contrasena_invalida_el_paso_intermedio(self):
        self.configurar()
        desafio = self.login().json()
        self.tecnico.set_password('Otra-clave-distinta-456!')
        self.tecnico.save()
        self.assertEqual(self.codigo(desafio['mfa_token'], '123456').json()['code'], 'mfa_vencido')

    # ------------------------------------------------------------------ app móvil

    def test_app_movil_recibe_su_sesion_de_solo_lectura_y_la_llave_tras_el_codigo(self):
        self.configurar()
        desafio = self.login(canal='movil').json()
        import time  # el código del intervalo actual ya se usó al configurar: se usa el siguiente
        codigo = mfa._hotp(self.ajustes().mfa_secreto, int(time.time() // 30) + 1)
        datos = self.codigo(desafio['mfa_token'], codigo).json()
        self.assertTrue(AccessToken(datos['access'])['solo_lectura'])
        self.assertIn('llave', datos)

    def test_la_huella_no_salta_una_verificacion_recien_exigida(self):
        llave = self.login(canal='movil').json()['llave']
        self.accion('exigir')
        cache.clear()
        r = APIClient().post('/api/auth/token/dispositivo/', {'llave': llave}, format='json')
        self.assertEqual(r.status_code, 401)

    # ------------------------------------------------------------------ administración

    def test_restablecer_pide_configurar_de_nuevo_y_quitar_deja_de_pedirla(self):
        self.configurar()
        secreto_anterior = self.ajustes().mfa_secreto
        self.assertEqual(self.accion('restablecer').json(), {'mfa': 'pendiente'})
        desafio = self.login().json()
        self.assertEqual(desafio['mfa'], 'configurar')
        self.assertNotEqual(desafio['secreto'], secreto_anterior)

        self.assertEqual(self.accion('quitar').json(), {'mfa': 'no'})
        self.assertIn('access', self.login().json())
        self.assertEqual(self.ajustes().mfa_secreto, '')

    def test_el_estado_se_ve_en_la_lista_de_usuarios(self):
        self.accion('exigir')
        datos = self.login('admin').json()
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {datos['access']}")
        lista = {u['username']: u['mfa'] for u in api.get('/api/auth/users/').json()}
        self.assertEqual((lista['tecnico'], lista['admin']), ('pendiente', 'no'))

    def test_el_administrador_comun_no_puede_cambiarla(self):
        self.assertEqual(self.accion('exigir', quien='admin').status_code, 403)
        self.assertFalse(self.ajustes().mfa_requerida)
