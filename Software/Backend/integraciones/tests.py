import json
import smtplib
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from requests.structures import CaseInsensitiveDict
from rest_framework.test import APIClient

from accesos.models import PuntoAcceso
from accesos.views import autenticar_lector
from intervenciones.buzon import MensajeInvalido, procesar_mensaje
from mediciones.models import Medicion, Sensor, Ubicacion
from mediciones.tests import TablasNoGestionadasTestCase

from . import actividad, pruebas, secretos
from .models import ActividadIntegracion, RenovacionSecreto, SecretoIntegracion


User = get_user_model()
URL_ESTADO = '/api/sistema/integraciones/'
CLAVE = 'clave-de-prueba-123'


def url_renovar(nombre):
    return f'/api/integraciones/secretos/{nombre}/renovar/'


def usuario_con_rol(username, rol, email=''):
    usuario = User.objects.create_user(username=username, password=CLAVE, email=email, first_name=username.title())
    usuario.groups.set([Group.objects.get_or_create(name=rol)[0]])
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return usuario, cliente


@override_settings(ZABBIX_WEBHOOK_SECRET='secreto-del-env')
class SecretosTests(TestCase):
    def setUp(self):
        self.usuario, _ = usuario_con_rol('priv', 'AdministradorPrivilegiado')

    def test_sin_renovar_vale_el_del_env(self):
        self.assertTrue(secretos.verificar(secretos.WEBHOOK_ZABBIX, 'secreto-del-env'))
        self.assertFalse(secretos.verificar(secretos.WEBHOOK_ZABBIX, 'otro'))
        self.assertFalse(secretos.verificar(secretos.WEBHOOK_ZABBIX, ''))

    @override_settings(ZABBIX_WEBHOOK_SECRET='')
    def test_sin_configurar_no_acepta_nada(self):
        self.assertFalse(secretos.configurado(secretos.WEBHOOK_ZABBIX))
        self.assertFalse(secretos.verificar(secretos.WEBHOOK_ZABBIX, ''))

    def test_renovar_guarda_solo_el_hash_y_el_anterior_sirve_durante_la_gracia(self):
        nuevo, fila = secretos.renovar(secretos.WEBHOOK_ZABBIX, self.usuario, '127.0.0.1')

        self.assertTrue(secretos.verificar(secretos.WEBHOOK_ZABBIX, nuevo))
        self.assertTrue(secretos.verificar(secretos.WEBHOOK_ZABBIX, 'secreto-del-env'))
        guardado = ' '.join(str(v) for v in SecretoIntegracion.objects.values().get().values())
        self.assertNotIn(nuevo, guardado)
        self.assertNotIn('secreto-del-env', guardado)
        self.assertAlmostEqual(fila.anterior_valido_hasta, timezone.now() + secretos.GRACIA, delta=timedelta(minutes=1))

        SecretoIntegracion.objects.update(anterior_valido_hasta=timezone.now() - timedelta(seconds=1))
        self.assertFalse(secretos.verificar(secretos.WEBHOOK_ZABBIX, 'secreto-del-env'))
        self.assertTrue(secretos.verificar(secretos.WEBHOOK_ZABBIX, nuevo))

    def test_renovar_de_inmediato_anula_el_anterior(self):
        nuevo, fila = secretos.renovar(secretos.WEBHOOK_ZABBIX, self.usuario, '127.0.0.1', inmediato=True)

        self.assertIsNone(fila.anterior_valido_hasta)
        self.assertFalse(secretos.verificar(secretos.WEBHOOK_ZABBIX, 'secreto-del-env'))
        self.assertTrue(secretos.verificar(secretos.WEBHOOK_ZABBIX, nuevo))

    def test_una_segunda_renovacion_deja_como_anterior_la_primera(self):
        primero, _ = secretos.renovar(secretos.WEBHOOK_ZABBIX, self.usuario, '127.0.0.1')
        segundo, _ = secretos.renovar(secretos.WEBHOOK_ZABBIX, self.usuario, '127.0.0.1')

        self.assertTrue(secretos.verificar(secretos.WEBHOOK_ZABBIX, segundo))
        self.assertTrue(secretos.verificar(secretos.WEBHOOK_ZABBIX, primero))
        self.assertFalse(secretos.verificar(secretos.WEBHOOK_ZABBIX, 'secreto-del-env'))
        self.assertEqual(RenovacionSecreto.objects.count(), 2)


@override_settings(INTERVENCIONES_TOKEN='token-del-env', ALERTAS_CORREO_ASINCRONO=False)
class RenovacionApiTests(TestCase):
    def setUp(self):
        cache.clear()  # el límite de intentos se guarda en la caché
        self.priv, self.cliente = usuario_con_rol('priv', 'AdministradorPrivilegiado', 'priv@example.com')
        usuario_con_rol('otro', 'AdministradorPrivilegiado', 'otro@example.com')

    def renovar(self, cliente=None, **extra):
        datos = {'password': CLAVE, **extra.pop('datos', {})}
        return (cliente or self.cliente).post(url_renovar(secretos.FLUJO_INTERVENCIONES), datos, format='json', **extra)

    def test_privilegiado_renueva_con_su_contrasena_y_se_avisa_sin_el_valor(self):
        respuesta = self.renovar()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Cache-Control'], 'no-store')
        nuevo = respuesta.data['secreto']
        self.assertTrue(secretos.verificar(secretos.FLUJO_INTERVENCIONES, nuevo))
        self.assertIsNotNone(respuesta.data['anterior_valido_hasta'])
        registro = RenovacionSecreto.objects.get()
        self.assertEqual((registro.usuario_id, registro.ip, registro.inmediato), (self.priv.id, '127.0.0.1', False))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(sorted(mail.outbox[0].bcc), ['otro@example.com', 'priv@example.com'])
        self.assertIn('token del flujo', mail.outbox[0].subject)
        self.assertNotIn(nuevo, mail.outbox[0].body)

    def test_renovar_de_inmediato(self):
        respuesta = self.renovar(datos={'inmediato': True})

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.data['anterior_valido_hasta'])
        self.assertFalse(secretos.verificar(secretos.FLUJO_INTERVENCIONES, 'token-del-env'))

    def test_el_administrador_no_puede_renovar(self):
        _, admin = usuario_con_rol('admin', 'Administrador')
        self.assertEqual(self.renovar(admin).status_code, 403)
        self.assertFalse(SecretoIntegracion.objects.exists())

    def test_contrasena_incorrecta_no_cambia_nada(self):
        respuesta = self.renovar(datos={'password': 'equivocada'})

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(SecretoIntegracion.objects.exists())
        self.assertTrue(secretos.verificar(secretos.FLUJO_INTERVENCIONES, 'token-del-env'))

    def test_a_traves_del_tunel_se_rechaza(self):
        respuesta = self.renovar(HTTP_CF_CONNECTING_IP='203.0.113.9')

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(SecretoIntegracion.objects.exists())

    def test_secreto_desconocido(self):
        respuesta = self.cliente.post(url_renovar('secret_key'), {'password': CLAVE}, format='json')
        self.assertEqual(respuesta.status_code, 404)


@override_settings(
    ZABBIX_WEBHOOK_SECRET='webhook-del-env',
    INTERVENCIONES_TOKEN='token-del-env',
    INTERVENCIONES_CORREO_FLUJO='flujo@example.com',
)
class WebhookYBuzonUsanElSecretoRenovadoTests(TestCase):
    def setUp(self):
        self.usuario, _ = usuario_con_rol('priv', 'AdministradorPrivilegiado')

    def test_webhook_acepta_el_renovado_y_cuenta_los_rechazos(self):
        nuevo, _ = secretos.renovar(secretos.WEBHOOK_ZABBIX, self.usuario, '127.0.0.1', inmediato=True)
        cliente = APIClient()
        url = '/api/integraciones/zabbix/webhook/'

        rechazado = cliente.post(url, [], format='json', HTTP_X_ZABBIX_TOKEN='webhook-del-env')
        # Con el token correcto pasa la verificación y llega a validar el cuerpo (una lista no sirve).
        aceptado = cliente.post(url, [], format='json', HTTP_X_ZABBIX_TOKEN=nuevo)

        self.assertEqual(rechazado.status_code, 403)
        self.assertEqual(aceptado.status_code, 400)
        self.assertEqual(ActividadIntegracion.objects.get(clave=actividad.WEBHOOK_ZABBIX).rechazos, 1)

    def test_buzon_acepta_el_renovado(self):
        nuevo, _ = secretos.renovar(secretos.FLUJO_INTERVENCIONES, self.usuario, '127.0.0.1', inmediato=True)

        def correo(token):
            return procesar_mensaje('Flujo <flujo@example.com>', '[SICMA-INT] prueba',
                                    json.dumps({'tipo': 'otro', 'token': token}))

        with self.assertRaisesMessage(MensajeInvalido, 'Token no válido'):
            correo('token-del-env')
        with self.assertRaisesMessage(MensajeInvalido, 'Tipo de mensaje desconocido'):
            correo(nuevo)


class LatidoDeLosProcesosTests(TestCase):
    clave = actividad.clave_proceso('procesar_intervenciones')

    @mock.patch('intervenciones.management.commands.procesar_intervenciones.leer_buzon', return_value=([], []))
    def test_cada_pasada_deja_un_latido(self, _):
        call_command('procesar_intervenciones', una_vez=True, stdout=StringIO())

        latido = ActividadIntegracion.objects.get(clave=self.clave)
        self.assertIsNotNone(latido.ultimo_exito)
        self.assertEqual(latido.ultimo_error, '')

    @mock.patch('intervenciones.management.commands.procesar_intervenciones.leer_buzon',
                side_effect=RuntimeError('Faltan EMAIL_HOST_USER o EMAIL_HOST_PASSWORD para leer el buzón.'))
    def test_una_pasada_fallida_queda_registrada(self, _):
        with self.assertRaises(RuntimeError):
            call_command('procesar_intervenciones', una_vez=True, stdout=StringIO())

        latido = ActividadIntegracion.objects.get(clave=self.clave)
        self.assertIsNone(latido.ultimo_exito)
        self.assertIn('Faltan EMAIL_HOST_USER', latido.ultimo_error)


@override_settings(
    ZABBIX_WEBHOOK_SECRET='webhook-del-env-secreto',
    INTERVENCIONES_TOKEN='token-del-env-secreto',
    INTERVENCIONES_CORREO_FLUJO='flujo@example.com',
    EMAIL_HOST_USER='sicma.alertas@example.com',
    EMAIL_HOST_PASSWORD='clave-de-aplicacion',
    ZABBIX_URL='http://10.0.0.5/zabbix/api_jsonrpc.php',
    ZABBIX_TOKEN='token-zabbix-secreto',
)
class EstadoTests(TablasNoGestionadasTestCase):
    modelos = (Ubicacion, Sensor, Medicion, PuntoAcceso)

    def setUp(self):
        self.sala = Ubicacion.objects.create(sala='Sala principal', zona='Zona A')
        _, self.admin = usuario_con_rol('admin', 'Administrador')

    def test_el_administrador_ve_el_estado_sin_ningun_secreto(self):
        Sensor.objects.create(codigo='arduino-01', tipo='ESP32', ubicacion=self.sala, estado='Activo',
                              intervalo_esperado_segundos=60, device_key_hash='x')

        respuesta = self.admin.get(URL_ESTADO)

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertTrue(datos['red_local'])
        self.assertFalse(datos['puede_renovar'])
        self.assertEqual(datos['webhook']['secreto']['origen'], 'env')
        self.assertTrue(datos['buzon']['configurado'])
        self.assertEqual(datos['correo']['cuenta'], 'si•••@example.com')
        self.assertEqual(datos['sensores'], {'en_linea': 0, 'sin_datos': 1, 'inactivos': 0})
        texto = respuesta.content.decode()
        for secreto in ('webhook-del-env-secreto', 'token-del-env-secreto', 'clave-de-aplicacion',
                        'token-zabbix-secreto', 'sicma.alertas', '10.0.0.5'):
            self.assertNotIn(secreto, texto)

    def test_el_tecnico_no_ve_las_integraciones(self):
        _, tecnico = usuario_con_rol('tecnico', 'Tecnico')
        self.assertEqual(tecnico.get(URL_ESTADO).status_code, 403)

    def test_a_traves_del_tunel_no_se_ofrece_renovar(self):
        _, priv = usuario_con_rol('priv', 'AdministradorPrivilegiado')

        datos = priv.get(URL_ESTADO, HTTP_CF_CONNECTING_IP='203.0.113.9').json()

        self.assertTrue(datos['puede_renovar'])
        self.assertFalse(datos['red_local'])

    def test_un_lector_que_se_autentica_aparece_en_linea(self):
        punto = PuntoAcceso.objects.create(nombre='Puerta', ubicacion=self.sala, estado='Activo',
                                           device_key_hash=make_password('clave-lector'))
        cache.clear()
        peticion = RequestFactory().get('/', HTTP_X_PUNTO_ACCESO=str(punto.id), HTTP_X_DEVICE_KEY='clave-lector')
        self.assertEqual(autenticar_lector(peticion), punto)

        lector = self.admin.get(URL_ESTADO).json()['lectores'][0]

        self.assertTrue(lector['en_linea'])
        self.assertIsNotNone(lector['ultimo_contacto'])


def respuesta_http(status=200, cuerpo=None, cabeceras=None):
    r = mock.Mock(status_code=status, headers=CaseInsensitiveDict(cabeceras or {}))
    r.json.return_value = cuerpo or {}
    r.raise_for_status.return_value = None
    return r


class PruebasTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(ZABBIX_URL='http://10.0.0.5/zabbix/api_jsonrpc.php', ZABBIX_TOKEN='token-zabbix')
    @mock.patch('infraestructura.zabbix_client.requests.post')
    def test_zabbix_token_rechazado_sin_exponer_datos(self, post):
        post.side_effect = [
            respuesta_http(cuerpo={'result': '7.0.31'}),
            respuesta_http(cuerpo={'error': {'message': 'Application error.', 'data': 'Not authorized.'}}),
        ]

        resultado = pruebas.probar_zabbix()

        self.assertFalse(resultado['ok'])
        self.assertIn('rechazó el token', resultado['detalle'])
        self.assertNotIn('10.0.0.5', resultado['detalle'])
        self.assertNotIn('token-zabbix', resultado['detalle'])
        self.assertNotIn('Authorization', post.call_args_list[0].kwargs['headers'])  # la versión va sin token

    @override_settings(ZABBIX_URL='http://zabbix/api_jsonrpc.php', ZABBIX_TOKEN='token-zabbix')
    @mock.patch('infraestructura.zabbix_client.requests.post')
    def test_zabbix_ok(self, post):
        post.side_effect = [respuesta_http(cuerpo={'result': '7.0.31'}), respuesta_http(cuerpo={'result': []})]

        resultado = pruebas.probar_zabbix()

        self.assertTrue(resultado['ok'])
        self.assertIn('7.0.31', resultado['detalle'])

    @override_settings(URL_PUBLICA_API='https://api.ejemplo.cl/api')
    @mock.patch('integraciones.pruebas.requests.get')
    def test_tunel_detecta_una_ruta_interna_expuesta(self, get):
        def responder(url, timeout):
            if url.endswith('/auth/me/'):
                return respuesta_http(401, cabeceras={'CF-RAY': 'abc'})
            return respuesta_http(405 if '/accesos/lector/' in url else 404)
        get.side_effect = responder

        resultado = pruebas.probar_tunel()

        self.assertFalse(resultado['ok'])
        self.assertEqual(resultado['expuestas'], ['/api/accesos/lector/intentos/'])

    @override_settings(URL_PUBLICA_API='https://api.ejemplo.cl/api')
    @mock.patch('integraciones.pruebas.requests.get')
    def test_tunel_ok(self, get):
        get.side_effect = lambda url, timeout: respuesta_http(
            401 if url.endswith('/auth/me/') else 404, cabeceras={'CF-RAY': 'abc'})

        resultado = pruebas.probar_tunel()

        self.assertTrue(resultado['ok'])
        self.assertIn('api.ejemplo.cl', resultado['detalle'])

    @override_settings(EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_correo_sin_configurar(self):
        self.assertFalse(pruebas.probar_correo()['ok'])

    @override_settings(EMAIL_HOST_USER='sicma@example.com', EMAIL_HOST_PASSWORD='clave-app')
    @mock.patch('integraciones.pruebas.imaplib.IMAP4_SSL')
    @mock.patch('integraciones.pruebas.smtplib.SMTP')
    def test_correo_rechazado_para_enviar(self, smtp, imap):
        smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b'no')

        resultado = pruebas.probar_correo()

        self.assertFalse(resultado['ok'])
        self.assertFalse(resultado['envio']['ok'])
        self.assertTrue(resultado['lectura']['ok'])
        self.assertNotIn('clave-app', json.dumps(resultado, default=str))

    def test_api_probar(self):
        _, admin = usuario_con_rol('admin', 'Administrador')
        _, tecnico = usuario_con_rol('tecnico', 'Tecnico')
        falso = {'ok': True, 'detalle': 'Zabbix 7 respondió.'}
        with mock.patch.dict(pruebas.PRUEBAS, {'zabbix': lambda: falso}):
            respuesta = admin.post('/api/sistema/integraciones/zabbix/probar/')
            self.assertEqual(tecnico.post('/api/sistema/integraciones/zabbix/probar/').status_code, 403)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data, falso)
        self.assertEqual(admin.post('/api/sistema/integraciones/otra/probar/').status_code, 404)
