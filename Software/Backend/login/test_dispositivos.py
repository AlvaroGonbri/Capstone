"""Rutas de dispositivos de SICMA: solo aceptan la credencial correcta de SU dispositivo.

    python manage.py test login.test_dispositivos -v 2
    SICMA_DISPOSITIVOS_CSV=dispositivos.csv python manage.py test login.test_dispositivos   # + evidencia

Complementa test_matriz_permisos.py, que deja fuera estas 12 rutas porque no usan roles:

  ESP32 (sensores)   POST /api/mediciones/                     sensor_codigo (cuerpo) + X-Device-Key
  Lector biométrico  10 rutas /api/accesos/lector/...          X-Punto-Acceso + X-Device-Key
  Zabbix             POST /api/integraciones/zabbix/webhook/   X-Zabbix-Token (secreto compartido)

Casos por ruta (los que no aplican quedan como OMITIDO, con el motivo):
  1. control_positivo      credencial correcta                  -> 2xx (prueba que el resto no falla "por casualidad")
  2. sin_clave             sin la cabecera de la clave          -> 401/403
  3. clave_incorrecta      clave inventada                      -> 401/403
  4. clave_vacia           cabecera presente pero vacía         -> 401/403
  5. clave_de_otro_tipo    clave válida de OTRO tipo de equipo  -> 401/403 (la del lector no sirve para el sensor)
  6. dispositivo_inactivo  clave correcta de un equipo inactivo -> 401/403
  7. jwt_de_usuario        JWT de un administrador, sin clave   -> 401/403 (no aceptan sesión de usuario)
  8. suplantacion          credencial de A haciéndose pasar por B -> rechazo, y B no queda con datos ni
                                                                     trabajos tocados
  9. clave_en_url          clave en ?key= en vez de cabecera    -> 401/403 (las URLs quedan en los logs)
"""
import csv
import os
import uuid

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accesos.models import (
    ACTIVO, INACTIVO, BajaHuella, PersonaAutorizada, PuntoAcceso, SolicitudEnrolamiento, SolicitudVerificacion,
)
from mediciones.models import Medicion, Sensor, Ubicacion

from .serializers import EmailTokenObtainPairSerializer

SECRETO_ZABBIX = 'secreto-webhook-de-prueba-' + 'z' * 24
RECHAZO = (401, 403)


@override_settings(
    ZABBIX_WEBHOOK_SECRET=SECRETO_ZABBIX, ZABBIX_URL='', ZABBIX_TOKEN='', GEMINI_API_KEY='',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', ALERTAS_CORREO_ASINCRONO=False,
)
class RutasDispositivosTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.no_gestionados = [m for m in apps.get_models() if not m._meta.managed]
        with connection.schema_editor() as editor:
            for modelo in cls.no_gestionados:
                editor.create_model(modelo)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            for modelo in reversed(cls.no_gestionados):
                editor.delete_model(modelo)

    def setUp(self):
        self.sala = Ubicacion.objects.create(sala='Sala de prueba', zona='Zona A')
        self.contador = 0
        admin = get_user_model().objects.create_user(username='admin_dispositivos', password='Clave-de-prueba-123!')
        admin.groups.set([Group.objects.get_or_create(name='AdministradorPrivilegiado')[0]])
        self.jwt_admin = str(EmailTokenObtainPairSerializer.get_token(admin).access_token)

    # ------------------------------------------------------------------ dispositivos de prueba
    def nuevo(self, prefijo):
        self.contador += 1
        return f'{prefijo}-{self.contador}'

    def sensor(self, activo=True):
        clave = uuid.uuid4().hex
        sensor = Sensor.objects.create(
            codigo=self.nuevo('esp32'), tipo='ESP32', ubicacion=self.sala, intervalo_esperado_segundos=60,
            estado='Activo' if activo else 'Inactivo', device_key_hash=make_password(clave),
        )
        return sensor, clave

    def punto(self, activo=True):
        clave = uuid.uuid4().hex
        punto = PuntoAcceso.objects.create(
            nombre=self.nuevo('lector'), ubicacion=self.sala, estado=ACTIVO if activo else INACTIVO,
            device_key_hash=make_password(clave),
        )
        return punto, clave

    def persona(self):
        ident = self.nuevo('PER')
        return PersonaAutorizada.objects.create(nombre=f'Persona {ident}', identificador_biometrico_externo=ident)

    def trabajo(self, tipo, punto):
        """Un trabajo abierto del agente (enrolar, verificar o borrar una huella) para ese lector."""
        ahora = timezone.now()
        if tipo == 'enrolamiento':
            return SolicitudEnrolamiento.objects.create(persona=self.persona(), punto_acceso=punto, fecha_solicitud=ahora)
        if tipo == 'verificacion':
            return SolicitudVerificacion.objects.create(persona=self.persona(), punto_acceso=punto, fecha_solicitud=ahora)
        persona = self.persona()
        return BajaHuella.objects.create(punto_acceso=punto, identificador=persona.identificador_biometrico_externo,
                                         nombre=persona.nombre, fecha_solicitud=ahora)

    # ------------------------------------------------------------------ peticiones
    def pedir(self, metodo, url, datos=None, cabeceras=None, jwt=None):
        cache.clear()
        cliente = APIClient()
        if jwt:
            cliente.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt}')
        extra = {f'HTTP_{k.upper().replace("-", "_")}': v for k, v in (cabeceras or {}).items()}
        if metodo == 'GET':
            return cliente.get(url, **extra).status_code
        return cliente.post(url, datos or {}, format='json', **extra).status_code

    # ------------------------------------------------------------------ prueba
    def test_rutas_de_dispositivos(self):
        filas, fallas = [], []

        def registrar(ruta, caso, esperado, obtenido, ok, nota=''):
            filas.append([ruta, caso, esperado, obtenido, 'OK' if ok else 'FALLA', nota])
            if not ok:
                fallas.append(f'{ruta:48} {caso:22} esperado={esperado:22} obtenido={obtenido} {nota}')

        def omitir(ruta, caso, motivo):
            filas.append([ruta, caso, '-', '-', 'OMITIDO', motivo])

        def rechazo(ruta, caso, codigo, nota=''):
            registrar(ruta, caso, '401/403', codigo, codigo in RECHAZO, nota)

        self.probar_esp32(registrar, rechazo)
        self.probar_lector(registrar, rechazo)
        self.probar_zabbix(registrar, rechazo, omitir)

        destino = os.environ.get('SICMA_DISPOSITIVOS_CSV')
        if destino:
            with open(destino, 'w', newline='', encoding='utf-8-sig') as archivo:
                escritor = csv.writer(archivo, delimiter=';')
                escritor.writerow(['ruta', 'caso', 'esperado', 'obtenido', 'resultado', 'nota'])
                escritor.writerows(filas)
        casos = sum(1 for f in filas if f[4] in ('OK', 'FALLA'))
        print(f'\nRutas de dispositivos: {casos - len(fallas)}/{casos} casos OK'
              + (f' -> {os.path.abspath(destino)}' if destino else ''))
        self.assertFalse(fallas, f'\n{len(fallas)} casos fallaron:\n' + '\n'.join(fallas))

    # ESP32 ------------------------------------------------------------------------------------------
    def probar_esp32(self, registrar, rechazo):
        ruta, url = 'POST /api/mediciones/', '/api/mediciones/'

        def lectura(sensor):
            return {'sensor_codigo': sensor.codigo, 'evento_id': str(uuid.uuid4()),
                    'temperatura': '22.50', 'humedad': '45.00', 'fecha_hora_medicion': timezone.now().isoformat()}

        a, clave_a = self.sensor()
        b, _ = self.sensor()
        codigo = self.pedir('POST', url, lectura(a), {'X-Device-Key': clave_a})
        registrar(ruta, 'control_positivo', '2xx', codigo, 200 <= codigo < 300)
        rechazo(ruta, 'sin_clave', self.pedir('POST', url, lectura(a)))
        rechazo(ruta, 'clave_incorrecta', self.pedir('POST', url, lectura(a), {'X-Device-Key': 'x' * 32}))
        rechazo(ruta, 'clave_vacia', self.pedir('POST', url, lectura(a), {'X-Device-Key': ''}))
        _, clave_lector = self.punto()
        rechazo(ruta, 'clave_de_otro_tipo', self.pedir('POST', url, lectura(a), {'X-Device-Key': clave_lector}),
                'clave de un lector')
        inactivo, clave_inactivo = self.sensor(activo=False)
        rechazo(ruta, 'dispositivo_inactivo', self.pedir('POST', url, lectura(inactivo), {'X-Device-Key': clave_inactivo}))
        rechazo(ruta, 'jwt_de_usuario', self.pedir('POST', url, lectura(a), jwt=self.jwt_admin))
        antes = Medicion.objects.filter(sensor=b).count()
        codigo = self.pedir('POST', url, lectura(b), {'X-Device-Key': clave_a})  # clave de A, dice ser B
        sin_cambios = Medicion.objects.filter(sensor=b).count() == antes
        registrar(ruta, 'suplantacion', 'rechazo y B sin datos', codigo, codigo in RECHAZO and sin_cambios,
                  'clave del sensor A con el código del sensor B')
        rechazo(ruta, 'clave_en_url', self.pedir('POST', f'{url}?key={clave_a}', lectura(a)))

    # Lector biométrico --------------------------------------------------------------------------------
    def probar_lector(self, registrar, rechazo):
        intento = lambda: {'evento_id': str(uuid.uuid4()), 'estado': 'sin_coincidencia'}  # noqa: E731
        # (ruta, método, tipo de trabajo o None, sufijo de la URL, cuerpo)
        rutas = [
            ('intentos/', 'POST', None, None, intento),
            ('enrolamientos/siguiente/', 'GET', 'enrolamiento', None, None),
            ('enrolamientos/{pk}/progreso/', 'POST', 'enrolamiento', 'progreso',
             lambda: {'muestra': 1, 'total_muestras': 3, 'indicacion': 'Apoya el dedo'}),
            ('enrolamientos/{pk}/resultado/', 'POST', 'enrolamiento', 'resultado', lambda: {'exito': False, 'mensaje': 'prueba'}),
            ('verificaciones/siguiente/', 'GET', 'verificacion', None, None),
            ('verificaciones/{pk}/progreso/', 'POST', 'verificacion', 'progreso',
             lambda: {'intento': 1, 'total_intentos': 3, 'indicacion': 'Apoya el dedo'}),
            ('verificaciones/{pk}/resultado/', 'POST', 'verificacion', 'resultado', lambda: {'coincide': False}),
            ('bajas/siguiente/', 'GET', 'baja', None, None),
            ('bajas/{pk}/resultado/', 'POST', 'baja', 'resultado', lambda: {'exito': True, 'mensaje': 'prueba'}),
        ]
        for sufijo, metodo, tipo, accion, cuerpo in rutas:
            ruta = f'{metodo} /api/accesos/lector/{sufijo}'
            con_pk = '{pk}' in sufijo

            def url_para(punto):
                """URL de la ruta; si lleva {pk}, con un trabajo abierto NUEVO de ese lector."""
                base = f'/api/accesos/lector/{sufijo}'
                return base.format(pk=self.trabajo(tipo, punto).pk) if con_pk else base

            def pedir(punto, cabeceras=None, jwt=None, url=None):
                return self.pedir(metodo, url or url_para(punto), cuerpo() if cuerpo else None, cabeceras, jwt)

            def cred(punto, clave):
                return {'X-Punto-Acceso': str(punto.pk), 'X-Device-Key': clave}

            a, clave_a = self.punto()
            b, _ = self.punto()
            codigo = pedir(a, cred(a, clave_a))
            registrar(ruta, 'control_positivo', '2xx', codigo, 200 <= codigo < 300)
            rechazo(ruta, 'sin_clave', pedir(a, {'X-Punto-Acceso': str(a.pk)}))
            rechazo(ruta, 'clave_incorrecta', pedir(a, cred(a, 'x' * 32)))
            rechazo(ruta, 'clave_vacia', pedir(a, cred(a, '')))
            _, clave_sensor = self.sensor()
            rechazo(ruta, 'clave_de_otro_tipo', pedir(a, cred(a, clave_sensor)), 'clave de un sensor ESP32')
            inactivo, clave_inactivo = self.punto(activo=False)
            rechazo(ruta, 'dispositivo_inactivo', pedir(inactivo, cred(inactivo, clave_inactivo)))
            rechazo(ruta, 'jwt_de_usuario', pedir(a, jwt=self.jwt_admin))
            rechazo(ruta, 'clave_en_url',
                    pedir(a, {'X-Punto-Acceso': str(a.pk)}, url=f'{url_para(a)}?key={clave_a}'))

            # Suplantación 1: dice ser el lector B usando la clave del lector A.
            rechazo(ruta, 'suplantacion', pedir(b, cred(b, clave_a)), 'X-Punto-Acceso de B con la clave de A')

            # Suplantación 2: con SU credencial válida, A intenta tomar o modificar un trabajo de B.
            if tipo and not con_pk:
                trabajo_b = self.trabajo(tipo, b)
                codigo = self.pedir(metodo, f'/api/accesos/lector/{sufijo}', None, cred(a, clave_a))
                trabajo_b.refresh_from_db()
                intacto = trabajo_b.estado == 'Pendiente'
                registrar(ruta, 'trabajo_de_otro_lector', '204 y B intacto', codigo, codigo == 204 and intacto,
                          'A pide su siguiente trabajo y no recibe el de B')
            elif con_pk:
                trabajo_b = self.trabajo(tipo, b)
                url_b = f'/api/accesos/lector/{sufijo}'.format(pk=trabajo_b.pk)
                codigo = self.pedir(metodo, url_b, cuerpo(), cred(a, clave_a))
                trabajo_b.refresh_from_db()
                intacto = trabajo_b.estado == 'Pendiente' and getattr(trabajo_b, 'indicacion', '') == ''
                registrar(ruta, 'trabajo_de_otro_lector', '404 y B intacto', codigo, codigo == 404 and intacto,
                          'A intenta modificar un trabajo del lector B')

    # Zabbix ------------------------------------------------------------------------------------------
    def probar_zabbix(self, registrar, rechazo, omitir):
        ruta, url = 'POST /api/integraciones/zabbix/webhook/', '/api/integraciones/zabbix/webhook/'

        def evento():
            return {'event_id': str(10_000 + self.contador), 'host': 'srv-prueba', 'problem': 'Prueba de webhook',
                    'severity': 'High', 'status': 'PROBLEM'}

        codigo = self.pedir('POST', url, evento(), {'X-Zabbix-Token': SECRETO_ZABBIX})
        registrar(ruta, 'control_positivo', '2xx', codigo, 200 <= codigo < 300)
        rechazo(ruta, 'sin_clave', self.pedir('POST', url, evento()))
        rechazo(ruta, 'clave_incorrecta', self.pedir('POST', url, evento(), {'X-Zabbix-Token': 'x' * 32}))
        rechazo(ruta, 'clave_vacia', self.pedir('POST', url, evento(), {'X-Zabbix-Token': ''}))
        _, clave_lector = self.punto()
        rechazo(ruta, 'clave_de_otro_tipo', self.pedir('POST', url, evento(), {'X-Zabbix-Token': clave_lector}),
                'clave de un lector')
        omitir(ruta, 'dispositivo_inactivo', 'secreto compartido: no hay un equipo que activar o desactivar')
        rechazo(ruta, 'jwt_de_usuario', self.pedir('POST', url, evento(), jwt=self.jwt_admin))
        omitir(ruta, 'suplantacion', 'secreto compartido: no identifica a un equipo en particular')
        rechazo(ruta, 'clave_en_url', self.pedir('POST', f'{url}?key={SECRETO_ZABBIX}', evento()))
