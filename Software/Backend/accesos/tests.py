import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from mediciones.models import Ubicacion
from mediciones.tests import TablasNoGestionadasTestCase, cliente_con_rol

from .models import EventoAcceso, PermisoAcceso, PermisoDia, PersonaAutorizada, PuntoAcceso


SANTIAGO = ZoneInfo('America/Santiago')
# Miércoles 21/10/2026 a las 10:00 en Santiago.
MIERCOLES_10AM = datetime(2026, 10, 21, 10, 0, tzinfo=SANTIAGO)


@override_settings(SICMA_ZONA_HORARIA='America/Santiago')
class AccesosTestCase(TablasNoGestionadasTestCase):
    modelos = TablasNoGestionadasTestCase.modelos + (PersonaAutorizada, PuntoAcceso, PermisoAcceso, PermisoDia, EventoAcceso)

    def setUp(self):
        self.admin = cliente_con_rol('admin', 'Administrador')
        self.auditor = cliente_con_rol('auditor', 'Auditor')
        self.sala = Ubicacion.objects.create(sala='Sala principal')
        creado = self.admin.post('/api/accesos/puntos/', {'nombre': 'Puerta sala', 'ubicacion': self.sala.id}, format='json').json()
        self.punto = PuntoAcceso.objects.get(pk=creado['id'])
        self.clave = creado['clave_dispositivo']
        self.ana = PersonaAutorizada.objects.create(nombre='Ana Contratista', identificador_biometrico_externo='PER-001')

    def lector(self, clave=None, punto=None):
        cliente = APIClient()
        cliente.credentials(HTTP_X_PUNTO_ACCESO=str(punto or self.punto.id), HTTP_X_DEVICE_KEY=clave or self.clave)
        return cliente

    def intento(self, estado='coincide', identificador='PER-001', cuando=MIERCOLES_10AM, evento_id=None, **extra):
        datos = {'evento_id': str(evento_id or uuid.uuid4()), 'estado': estado, 'identificador': identificador, **extra}
        if cuando:
            datos['fecha_hora'] = cuando.isoformat()
        return self.lector().post('/api/accesos/lector/intentos/', datos, format='json')

    def permiso(self, persona=None, **extra):
        datos = {'persona': (persona or self.ana).id, 'punto_acceso': self.punto.id, 'vigencia_inicio': '2026-10-01', **extra}
        return self.admin.post('/api/accesos/permisos/', datos, format='json')


class DecisionTests(AccesosTestCase):
    def setUp(self):
        super().setUp()
        # Las fechas de prueba deben caer dentro de la ventana creíble (último día).
        self.ahora = timezone.now().astimezone(SANTIAGO)

    def test_permiso_vigente_permite_y_queda_registrado(self):
        self.permiso()
        respuesta = self.intento(cuando=None)
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual((respuesta.json()['resultado'], respuesta.json()['persona']), ('Permitido', 'Ana Contratista'))
        evento = EventoAcceso.objects.get()
        self.assertEqual((evento.persona, evento.punto_acceso, evento.identificador_biometrico_externo), (self.ana, self.punto, 'PER-001'))

    def test_motivos_de_denegacion(self):
        self.assertEqual(self.intento(cuando=None).json()['motivo'], 'Sin permiso vigente para este punto')
        self.assertEqual(self.intento('sin_coincidencia', '', cuando=None).json()['motivo'], 'Huella no reconocida')
        self.assertEqual(self.intento(identificador='OTRO', cuando=None).json()['motivo'], 'Identificador no registrado en SICMA')
        self.permiso()
        self.ana.estado = 'Inactivo'
        self.ana.save()
        self.assertEqual(self.intento(cuando=None).json()['motivo'], 'Persona desactivada')
        error = self.intento('error', '', cuando=None, motivo='Sensor sucio').json()
        self.assertEqual((error['resultado'], error['motivo']), ('Error', 'Falla del lector: Sensor sucio'))
        self.assertEqual(EventoAcceso.objects.filter(resultado='Denegado').count(), 4)
        self.assertEqual(EventoAcceso.objects.get(motivo='Huella no reconocida').identificador_biometrico_externo, 'desconocido')

    def test_permiso_revocado_o_vencido_deniega(self):
        permiso = self.permiso().json()
        self.admin.patch(f'/api/accesos/permisos/{permiso["id"]}/', {'estado': 'Revocado'}, format='json')
        self.assertEqual(self.intento(cuando=None).json()['resultado'], 'Denegado')
        ayer = (self.ahora - timedelta(days=1)).date().isoformat()
        self.permiso(vigencia_inicio='2026-01-01', vigencia_fin=ayer)
        self.assertEqual(self.intento(cuando=None).json()['motivo'], 'Sin permiso vigente para este punto')

    def test_ventanas_horarias_por_dia(self):
        from . import servicio

        self.permiso(dias=[{'dia_semana': 'Mie', 'hora_inicio': '08:00', 'hora_fin': '18:00'}])
        self.assertEqual(servicio.decidir(self.punto, 'coincide', 'PER-001', MIERCOLES_10AM).resultado, 'Permitido')
        self.assertEqual(servicio.decidir(self.punto, 'coincide', 'PER-001', MIERCOLES_10AM.replace(hour=20)).motivo, 'Fuera del horario autorizado')
        jueves = MIERCOLES_10AM + timedelta(days=1)
        self.assertEqual(servicio.decidir(self.punto, 'coincide', 'PER-001', jueves).resultado, 'Denegado')

    def test_ventana_que_cruza_la_medianoche(self):
        from . import servicio

        self.permiso(dias=[{'dia_semana': 'Mie', 'hora_inicio': '22:00', 'hora_fin': '02:00'}])
        self.assertEqual(servicio.decidir(self.punto, 'coincide', 'PER-001', MIERCOLES_10AM.replace(hour=23)).resultado, 'Permitido')
        self.assertEqual(servicio.decidir(self.punto, 'coincide', 'PER-001', MIERCOLES_10AM.replace(hour=1)).resultado, 'Permitido')
        self.assertEqual(servicio.decidir(self.punto, 'coincide', 'PER-001', MIERCOLES_10AM).resultado, 'Denegado')


class LectorTests(AccesosTestCase):
    def test_credenciales_del_lector(self):
        datos = {'evento_id': str(uuid.uuid4()), 'estado': 'sin_coincidencia'}
        self.assertEqual(self.lector(clave='mala').post('/api/accesos/lector/intentos/', datos, format='json').status_code, 401)
        self.assertEqual(self.lector(punto=999).post('/api/accesos/lector/intentos/', datos, format='json').status_code, 401)
        self.punto.estado = 'Inactivo'
        self.punto.save()
        self.assertEqual(self.lector().post('/api/accesos/lector/intentos/', datos, format='json').status_code, 401)

    def test_reintento_no_duplica(self):
        evento_id = uuid.uuid4()
        self.assertEqual(self.intento(cuando=None, evento_id=evento_id).status_code, 201)
        repetido = self.intento(cuando=None, evento_id=evento_id)
        self.assertEqual((repetido.status_code, repetido.json()['duplicado']), (200, True))
        self.assertEqual(EventoAcceso.objects.count(), 1)

    def test_coincidencia_exige_identificador_y_fecha_no_creible_usa_la_hora_de_llegada(self):
        self.assertIn('identificador', self.intento(identificador='', cuando=None).json())
        self.intento(cuando=timezone.now() + timedelta(days=3))
        self.assertLess(abs((EventoAcceso.objects.get().fecha_hora - timezone.now()).total_seconds()), 60)

    def test_nueva_clave_invalida_la_anterior(self):
        nueva = self.admin.post(f'/api/accesos/puntos/{self.punto.id}/clave/').json()['clave_dispositivo']
        datos = {'evento_id': str(uuid.uuid4()), 'estado': 'sin_coincidencia'}
        self.assertEqual(self.lector().post('/api/accesos/lector/intentos/', datos, format='json').status_code, 401)
        self.assertEqual(self.lector(clave=nueva).post('/api/accesos/lector/intentos/', datos, format='json').status_code, 201)
        self.assertNotIn('clave_dispositivo', self.auditor.get('/api/accesos/puntos/').json()[0])


class ConsultaYPermisosTests(AccesosTestCase):
    def test_auditor_consulta_y_filtra_pero_no_modifica(self):
        self.permiso()
        self.intento(cuando=None)
        self.intento('sin_coincidencia', '', cuando=None)

        todos = self.auditor.get('/api/accesos/eventos/').json()
        self.assertEqual(len(todos), 2)
        denegados = self.auditor.get('/api/accesos/eventos/', {'resultado': 'Denegado'}).json()
        self.assertEqual([e['motivo'] for e in denegados], ['Huella no reconocida'])
        self.assertEqual(len(self.auditor.get('/api/accesos/eventos/', {'q': 'ana'}).json()), 1)
        self.assertEqual(len(self.auditor.get('/api/accesos/eventos/', {'persona': self.ana.id}).json()), 1)
        hoy = timezone.now().astimezone(ZoneInfo('UTC')).date()
        self.assertEqual(len(self.auditor.get('/api/accesos/eventos/', {'desde': hoy, 'hasta': hoy}).json()), 2)

        self.assertEqual(self.auditor.post('/api/accesos/personas/', {'nombre': 'X', 'identificador_biometrico_externo': 'X'}, format='json').status_code, 403)
        self.assertEqual(self.auditor.post('/api/accesos/eventos/', {}, format='json').status_code, 405)

    def test_admin_asocia_persona_a_identificador_y_usuario(self):
        from django.contrib.auth import get_user_model

        usuario = get_user_model().objects.get(username='auditor')
        creada = self.admin.post('/api/accesos/personas/', {
            'nombre': 'Luis Técnico', 'identificador_biometrico_externo': ' PER-002 ', 'usuario': usuario.id,
        }, format='json')
        self.assertEqual(creada.status_code, 201)
        self.assertEqual((creada.json()['identificador_biometrico_externo'], creada.json()['usuario_nombre']), ('PER-002', 'auditor'))
        repetida = self.admin.post('/api/accesos/personas/', {'nombre': 'Otro', 'identificador_biometrico_externo': 'PER-002'}, format='json')
        self.assertEqual(repetida.status_code, 400)
        self.assertEqual(self.admin.post('/api/accesos/personas/', {'nombre': 'X', 'identificador_biometrico_externo': 'desconocido'}, format='json').status_code, 400)

    def test_permiso_con_ventanas_y_vigencia_valida(self):
        malo = self.permiso(vigencia_inicio='2026-10-10', vigencia_fin='2026-10-01')
        self.assertIn('vigencia_fin', malo.json())
        creado = self.permiso(dias=[{'dia_semana': 'Lun', 'hora_inicio': '08:00', 'hora_fin': '12:00'}]).json()
        self.assertEqual(creado['dias'][0]['dia_semana'], 'Lun')
        editado = self.admin.patch(f'/api/accesos/permisos/{creado["id"]}/', {
            'dias': [{'dia_semana': 'Mar', 'hora_inicio': '09:00', 'hora_fin': '10:00'}, {'dia_semana': 'Vie', 'hora_inicio': '09:00', 'hora_fin': '10:00'}],
        }, format='json').json()
        self.assertEqual([d['dia_semana'] for d in editado['dias']], ['Mar', 'Vie'])
        self.assertEqual(PermisoDia.objects.count(), 2)
        self.assertEqual(self.auditor.get('/api/accesos/permisos/', {'persona': self.ana.id}).json()[0]['persona_nombre'], 'Ana Contratista')
