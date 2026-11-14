from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Medicion, Sensor, Ubicacion, UmbralAmbiental


User = get_user_model()
URL = '/api/umbrales/'


def cliente_con_rol(username, rol):
    usuario = User.objects.create_user(username=username, password='clave')
    usuario.groups.set([Group.objects.get_or_create(name=rol)[0]])
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


class TablasNoGestionadasTestCase(TestCase):
    """Crea en la BD de pruebas las tablas managed=False (en producción las crea el script SQL)."""

    modelos = (Ubicacion, Sensor, Medicion, UmbralAmbiental)

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            for modelo in cls.modelos:
                editor.create_model(modelo)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            for modelo in reversed(cls.modelos):
                editor.delete_model(modelo)


class UmbralesTests(TablasNoGestionadasTestCase):
    def setUp(self):
        self.sala = Ubicacion.objects.create(sala='Sala principal', zona='Zona A')
        self.otra = Ubicacion.objects.create(sala='Sala B', zona='Zona B')
        self.admin = cliente_con_rol('admin', 'Administrador')

    def definir(self, ubicacion, variable, minimo, maximo, cliente=None):
        return (cliente or self.admin).post(URL, {
            'ubicacion': ubicacion.id, 'variable': variable,
            'valor_minimo': minimo, 'valor_maximo': maximo,
        }, format='json')

    def test_administrador_define_umbral_y_cada_cambio_crea_una_version(self):
        primera = self.definir(self.sala, 'Temperatura', 18, 27)
        segunda = self.definir(self.sala, 'Temperatura', 18, 25)

        self.assertEqual(primera.status_code, 201)
        self.assertEqual((primera.json()['version'], segunda.json()['version']), (1, 2))
        self.assertEqual(UmbralAmbiental.objects.count(), 2)  # la versión anterior se conserva

        vigentes = cliente_con_rol('tec', 'Tecnico').get(URL, {'ubicacion': self.sala.id}).json()
        self.assertEqual(len(vigentes), 1)
        self.assertEqual(Decimal(vigentes[0]['valor_maximo']), Decimal('25'))

    def test_historial_devuelve_todas_las_versiones_de_la_zona(self):
        self.definir(self.sala, 'Temperatura', 18, 27)
        self.definir(self.sala, 'Humedad', 35, 60)
        self.definir(self.sala, 'Temperatura', 18, 25)
        self.definir(self.otra, 'Temperatura', 15, 30)

        historial = cliente_con_rol('aud', 'Auditor').get(URL, {'ubicacion': self.sala.id, 'historial': 'true'}).json()

        self.assertEqual(
            [(u['variable'], u['version'], Decimal(u['valor_maximo'])) for u in historial],
            [('Temperatura', 2, Decimal('25')), ('Humedad', 1, Decimal('60')), ('Temperatura', 1, Decimal('27'))],
        )
        self.assertEqual(self.admin.get(URL, {'historial': 'true'}).status_code, 400)  # se pide por zona

    def test_sin_filtro_devuelve_los_vigentes_de_todas_las_zonas(self):
        self.definir(self.sala, 'Temperatura', 18, 27)
        self.definir(self.sala, 'Humedad', 35, 60)
        self.definir(self.otra, 'Temperatura', 15, 30)

        vigentes = self.admin.get(URL).json()

        self.assertEqual(
            sorted((u['ubicacion'], u['variable']) for u in vigentes),
            [(self.sala.id, 'Humedad'), (self.sala.id, 'Temperatura'), (self.otra.id, 'Temperatura')],
        )

    def test_rechaza_minimo_mayor_o_igual_al_maximo_y_valores_fuera_de_rango(self):
        self.assertEqual(self.definir(self.sala, 'Temperatura', 27, 18).status_code, 400)
        self.assertEqual(self.definir(self.sala, 'Temperatura', 20, 20).status_code, 400)
        self.assertEqual(self.definir(self.sala, 'Humedad', 10, 120).status_code, 400)
        self.assertEqual(self.definir(self.sala, 'Temperatura', -50, 20).status_code, 400)
        self.assertEqual(UmbralAmbiental.objects.count(), 0)

    def test_rechaza_variable_o_ubicacion_inexistente(self):
        respuesta = self.admin.post(URL, {
            'ubicacion': 999, 'variable': 'Presion', 'valor_minimo': 1, 'valor_maximo': 2,
        }, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('ubicacion', respuesta.json())
        self.assertIn('variable', respuesta.json())

    def test_solo_administradores_pueden_definir_umbrales(self):
        for rol in ('Tecnico', 'Jefatura', 'Auditor'):
            cliente = cliente_con_rol(f'u_{rol}', rol)
            self.assertEqual(self.definir(self.sala, 'Temperatura', 18, 27, cliente).status_code, 403)
            self.assertEqual(cliente.get(URL).status_code, 200)
        privilegiado = cliente_con_rol('priv', 'AdministradorPrivilegiado')
        self.assertEqual(self.definir(self.sala, 'Temperatura', 18, 27, privilegiado).status_code, 201)


class ConexionDeSensoresTests(TablasNoGestionadasTestCase):
    """El estado de conexión lo calcula el backend con la hora de recepción (no el navegador)."""

    def setUp(self):
        from django.utils import timezone

        self.ahora = timezone.now()
        self.sala = Ubicacion.objects.create(sala='Sala principal', zona='Zona A')
        self.cliente = cliente_con_rol('tec', 'Tecnico')

    def sensor(self, codigo, estado='Activo', intervalo=60):
        return Sensor.objects.create(
            codigo=codigo, tipo='ESP32', ubicacion=self.sala, estado=estado,
            intervalo_esperado_segundos=intervalo, device_key_hash='x',
        )

    def lectura(self, sensor, recibida_hace, medida_hace=None):
        from datetime import timedelta

        Medicion.objects.create(
            sensor=sensor, evento_id=f'{sensor.codigo}-{recibida_hace}', temperatura=22, humedad=45,
            fecha_hora_medicion=self.ahora - timedelta(seconds=medida_hace if medida_hace is not None else recibida_hace),
            fecha_hora_recepcion=self.ahora - timedelta(seconds=recibida_hace), origen='directo',
        )

    def conexiones(self):
        return {s['codigo']: s['conexion'] for s in self.cliente.get('/api/sensores/').json()}

    def test_estado_segun_la_ultima_lectura_recibida(self):
        reciente, atrasado, inactivo = self.sensor('ESP-1'), self.sensor('ESP-2'), self.sensor('ESP-3', estado='Inactivo')
        self.sensor('ESP-4')  # nunca envió lecturas
        self.lectura(reciente, recibida_hace=120)   # 2 intervalos: dentro de la tolerancia
        self.lectura(atrasado, recibida_hace=600)   # 10 intervalos: desconectado
        self.lectura(inactivo, recibida_hace=10)    # dado de baja: no es una falla

        self.assertEqual(self.conexiones(), {
            'ESP-1': 'En línea', 'ESP-2': 'Sin datos', 'ESP-3': 'Inactivo', 'ESP-4': 'Sin datos',
        })

    def test_lectura_antigua_recien_recibida_cuenta_como_en_linea(self):
        # El dispositivo reenvía lecturas guardadas mientras no tuvo red: si llegan ahora, está conectado.
        self.lectura(self.sensor('ESP-1'), recibida_hace=5, medida_hace=3600)

        self.assertEqual(self.conexiones()['ESP-1'], 'En línea')


class HistorialDeSensorTests(TablasNoGestionadasTestCase):
    """Gráfico de temperatura y humedad: lecturas promediadas por tramo (24 h / 7 d / 30 d)."""

    def setUp(self):
        from datetime import datetime, timezone as dt_timezone

        from django.utils import timezone

        self.sala = Ubicacion.objects.create(sala='Sala principal', zona='Zona A', rack='R1')
        self.sensor = Sensor.objects.create(
            codigo='arduino-01', tipo='ESP32', ubicacion=self.sala, estado='Activo',
            intervalo_esperado_segundos=60, device_key_hash='x',
        )
        self.cliente = cliente_con_rol('tec', 'Tecnico')
        # Inicio de un tramo de 10 minutos de hace una hora: las lecturas caen en tramos conocidos.
        segundos = int(timezone.now().timestamp()) // 600 * 600 - 3600
        self.tramo = datetime.fromtimestamp(segundos, tz=dt_timezone.utc)

    def lectura(self, segundos_desde_tramo, temperatura, humedad, sensor=None):
        from datetime import timedelta

        sensor = sensor or self.sensor
        fecha = self.tramo + timedelta(seconds=segundos_desde_tramo)
        Medicion.objects.create(
            sensor=sensor, evento_id=f'{sensor.codigo}-{segundos_desde_tramo}',
            temperatura=temperatura, humedad=humedad,
            fecha_hora_medicion=fecha, fecha_hora_recepcion=fecha, origen='Real',
        )

    def historial(self, rango=None, sensor=None):
        url = f'/api/sensores/{(sensor or self.sensor).id}/historial/'
        return self.cliente.get(url, {'rango': rango} if rango else {})

    def test_promedia_por_tramo_de_10_minutos_en_24_horas(self):
        self.lectura(60, Decimal('22.00'), Decimal('40.00'))
        self.lectura(120, Decimal('24.00'), None)            # humedad sin dato: no cuenta para su promedio
        self.lectura(700, Decimal('25.50'), Decimal('44.00'))  # tramo siguiente

        respuesta = self.historial()

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual((datos['rango'], datos['paso_segundos']), ('24h', 600))
        self.assertEqual(datos['sensor']['ubicacion'], 'Sala principal · Zona A · R1')
        primero, segundo = datos['puntos']
        self.assertEqual(primero['lecturas'], 2)
        self.assertEqual(
            (primero['temperatura'], primero['temperatura_min'], primero['temperatura_max']), (23.0, 22.0, 24.0),
        )
        self.assertEqual((primero['humedad'], primero['humedad_min'], primero['humedad_max']), (40.0, 40.0, 40.0))
        self.assertEqual((segundo['lecturas'], segundo['temperatura']), (1, 25.5))
        self.assertLess(primero['fecha'], segundo['fecha'])

    def test_solo_lecturas_del_sensor_y_del_periodo_pedido(self):
        otro = Sensor.objects.create(
            codigo='arduino-02', tipo='ESP32', ubicacion=self.sala, estado='Activo',
            intervalo_esperado_segundos=60, device_key_hash='x',
        )
        self.lectura(60, 22, 40)
        self.lectura(-3 * 86400, 21, 41)  # hace 3 días: fuera de 24 h, dentro de 7 d
        self.lectura(90, 30, 60, sensor=otro)

        self.assertEqual(len(self.historial('24h').json()['puntos']), 1)
        semana = self.historial('7d').json()
        self.assertEqual(semana['paso_segundos'], 3600)
        self.assertEqual([p['temperatura'] for p in semana['puntos']], [21.0, 22.0])

    def test_incluye_los_umbrales_vigentes_de_la_zona(self):
        from django.utils import timezone

        for version, maximo in ((1, 27), (2, 25)):
            UmbralAmbiental.objects.create(
                ubicacion=self.sala, variable='Temperatura', valor_minimo=18, valor_maximo=maximo,
                version=version, vigente_desde=timezone.now(),
            )

        umbrales = self.historial('30d').json()['umbrales']

        self.assertEqual(umbrales, {'temperatura': {'minimo': 18.0, 'maximo': 25.0}, 'humedad': None})

    def test_rechaza_rango_desconocido_y_sensor_inexistente(self):
        self.assertEqual(self.historial('1a').status_code, 400)
        self.assertEqual(self.cliente.get('/api/sensores/999/historial/').status_code, 404)

    def test_contratistas_no_ven_el_historial(self):
        self.cliente = cliente_con_rol('contratista', 'Contratistas')

        self.assertEqual(self.historial().status_code, 403)
