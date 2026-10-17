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
