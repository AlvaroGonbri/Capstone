"""Personal externo: ficha, habilitación manual y enrolamiento desde SICMA a través del agente."""
from datetime import timedelta

from django.utils import timezone

from mediciones.tests import cliente_con_rol

from .models import BajaHuella, EventoAcceso, PermisoAcceso, PersonaAutorizada, SolicitudEnrolamiento
from .tests import AccesosTestCase


class FichaYHabilitacionTests(AccesosTestCase):
    def setUp(self):
        super().setUp()
        self.contratistas = cliente_con_rol('contratos', 'Contratistas')

    def alta(self, **extra):
        datos = {'nombre': 'Juan Pérez', 'rut': '12.345.678-5', 'empresa': 'Clima Ltda.', **extra}
        return self.contratistas.post('/api/accesos/personas/', datos, format='json')

    def test_contratistas_registra_con_rut_validado_e_identificador_generado(self):
        respuesta = self.alta()
        self.assertEqual(respuesta.status_code, 201)
        datos = respuesta.json()
        self.assertEqual((datos['rut'], datos['empresa'], datos['estado']), ('12345678-5', 'Clima Ltda.', 'Activo'))
        self.assertEqual(datos['identificador_biometrico_externo'], f'EXT-{datos["id"]:05d}')
        self.assertIsNone(datos['huella_registrada_en'])

        self.assertIn('rut', self.alta(nombre='Otro').json())  # RUT repetido
        self.assertIn('dígito verificador', self.alta(rut='12.345.678-9').json()['rut'][0])

    def test_busqueda_por_palabra_clave(self):
        self.alta()
        self.alta(nombre='María Soto', rut='11.111.111-1', empresa='Redes SpA')
        buscar = lambda q: [p['nombre'] for p in self.auditor.get('/api/accesos/personas/', {'q': q}).json()]  # noqa: E731
        self.assertEqual(buscar('clima'), ['Juan Pérez'])
        self.assertEqual(buscar('11.111.111'), ['María Soto'])
        self.assertEqual(buscar('soto'), ['María Soto'])

    def test_deshabilitar_exige_motivo_y_queda_historial(self):
        persona = self.alta().json()
        url = f'/api/accesos/personas/{persona["id"]}/habilitacion/'

        self.assertIn('motivo', self.contratistas.post(url, {'habilitada': False}, format='json').json())
        respuesta = self.contratistas.post(url, {'habilitada': False, 'motivo': 'Cotizaciones vencidas'}, format='json')
        self.assertEqual(respuesta.json()['estado'], 'Inactivo')
        self.contratistas.post(url, {'habilitada': True, 'motivo': 'Cotizaciones al día'}, format='json')

        historial = self.auditor.get(url).json()
        self.assertEqual([(c['habilitada'], c['motivo'], c['usuario_nombre']) for c in historial],
                         [(True, 'Cotizaciones al día', 'contratos'), (False, 'Cotizaciones vencidas', 'contratos')])
        # El estado no se cambia por PATCH: solo con su historial.
        self.contratistas.patch(f'/api/accesos/personas/{persona["id"]}/', {'estado': 'Inactivo'}, format='json')
        self.assertEqual(PersonaAutorizada.objects.get(pk=persona['id']).estado, 'Activo')

    def test_permisos_de_los_roles(self):
        self.assertEqual(self.auditor.post('/api/accesos/personas/', {'nombre': 'X'}, format='json').status_code, 403)
        self.assertEqual(cliente_con_rol('jefe', 'Jefatura').get('/api/accesos/personas/').status_code, 200)
        # Contratistas ve su vista y los lectores, pero no el resto de SICMA.
        self.assertEqual(self.contratistas.get('/api/accesos/puntos/').status_code, 200)
        self.assertEqual(self.contratistas.get('/api/activos/').status_code, 403)
        self.assertEqual(self.contratistas.get('/api/accesos/eventos/').status_code, 403)
        self.assertEqual(self.contratistas.post('/api/accesos/puntos/', {'nombre': 'X', 'ubicacion': self.sala.id}, format='json').status_code, 403)


class EnrolamientoTests(AccesosTestCase):
    def setUp(self):
        super().setUp()
        self.contratistas = cliente_con_rol('contratos', 'Contratistas')
        self.persona = self.contratistas.post('/api/accesos/personas/', {'nombre': 'Juan Pérez', 'rut': '12.345.678-5'}, format='json').json()

    def siguiente(self, clave=None):
        return self.lector(clave=clave).get('/api/accesos/lector/enrolamientos/siguiente/')

    def test_ciclo_completo_sin_que_la_huella_viaje(self):
        solicitud = self.contratistas.post(f'/api/accesos/personas/{self.persona["id"]}/enrolar/', {}, format='json').json()
        self.assertEqual((solicitud['estado'], solicitud['punto_nombre']), ('Pendiente', 'Puerta sala'))

        trabajo = self.siguiente().json()
        self.assertEqual(trabajo, {'id': solicitud['id'], 'identificador': self.persona['identificador_biometrico_externo'], 'nombre': 'Juan Pérez'})
        self.assertEqual(self.siguiente().status_code, 204)  # ya está en curso: no se entrega dos veces
        self.assertEqual(self.contratistas.get(f'/api/accesos/enrolamientos/{solicitud["id"]}/').json()['estado'], 'EnCurso')

        progreso = {'muestra': 2, 'total_muestras': 3, 'indicacion': 'Apoya el dedo'}
        self.assertEqual(self.lector().post(f'/api/accesos/lector/enrolamientos/{solicitud["id"]}/progreso/', progreso, format='json').status_code, 204)
        en_curso = self.contratistas.get(f'/api/accesos/enrolamientos/{solicitud["id"]}/').json()
        self.assertEqual((en_curso['muestra'], en_curso['total_muestras'], en_curso['indicacion']), (2, 3, 'Apoya el dedo'))

        url = f'/api/accesos/lector/enrolamientos/{solicitud["id"]}/resultado/'
        self.assertEqual(self.lector().post(url, {'exito': True, 'mensaje': '3 muestras'}, format='json').json()['estado'], 'Completada')
        persona = self.auditor.get(f'/api/accesos/personas/{self.persona["id"]}/').json()
        self.assertIsNotNone(persona['huella_registrada_en'])
        self.assertEqual((persona['huella_registrada_por_nombre'], persona['enrolamiento']['estado']), ('contratos', 'Completada'))
        self.assertEqual(self.lector().post(url, {'exito': True}, format='json').status_code, 409)

    def test_huella_ya_enrolada_falla_con_el_motivo_del_agente(self):
        solicitud = self.contratistas.post(f'/api/accesos/personas/{self.persona["id"]}/enrolar/', {}, format='json').json()
        self.siguiente()
        self.lector().post(f'/api/accesos/lector/enrolamientos/{solicitud["id"]}/resultado/',
                           {'exito': False, 'mensaje': 'Esa huella ya está enrolada como EXT-00007'}, format='json')
        persona = self.auditor.get(f'/api/accesos/personas/{self.persona["id"]}/').json()
        self.assertIsNone(persona['huella_registrada_en'])
        self.assertEqual(persona['enrolamiento']['mensaje'], 'Esa huella ya está enrolada como EXT-00007')

    def test_una_solicitud_nueva_reemplaza_la_anterior_y_las_viejas_vencen(self):
        primera = self.contratistas.post(f'/api/accesos/personas/{self.persona["id"]}/enrolar/', {}, format='json').json()
        segunda = self.contratistas.post(f'/api/accesos/personas/{self.persona["id"]}/enrolar/', {}, format='json').json()
        self.assertEqual(SolicitudEnrolamiento.objects.get(pk=primera['id']).estado, 'Cancelada')
        SolicitudEnrolamiento.objects.filter(pk=segunda['id']).update(fecha_solicitud=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.siguiente().status_code, 204)
        self.assertEqual(SolicitudEnrolamiento.objects.get(pk=segunda['id']).estado, 'Fallida')

    def test_el_agente_debe_autenticarse(self):
        self.contratistas.post(f'/api/accesos/personas/{self.persona["id"]}/enrolar/', {}, format='json')
        self.assertEqual(self.siguiente(clave='mala').status_code, 401)
        self.assertEqual(self.auditor.post(f'/api/accesos/personas/{self.persona["id"]}/enrolar/', {}, format='json').status_code, 403)


class EliminarPersonaTests(AccesosTestCase):
    def setUp(self):
        super().setUp()
        self.contratistas = cliente_con_rol('contratos', 'Contratistas')
        self.persona = self.contratistas.post('/api/accesos/personas/', {'nombre': 'Juan Pérez', 'rut': '12.345.678-5'}, format='json').json()
        self.ident = self.persona['identificador_biometrico_externo']
        pk = self.persona['id']
        self.contratistas.post(f'/api/accesos/personas/{pk}/habilitacion/', {'habilitada': False, 'motivo': 'x'}, format='json')
        self.permiso(persona=PersonaAutorizada.objects.get(pk=pk), dias=[{'dia_semana': 'Lun', 'hora_inicio': '08:00', 'hora_fin': '18:00'}])
        self.intento(identificador=self.ident, cuando=None)

    def test_borra_la_ficha_conserva_los_accesos_y_ordena_borrar_la_huella(self):
        respuesta = self.contratistas.delete(f'/api/accesos/personas/{self.persona["id"]}/')
        self.assertEqual((respuesta.status_code, respuesta.json()['lectores_notificados']), (200, 1))

        self.assertFalse(PersonaAutorizada.objects.filter(pk=self.persona['id']).exists())
        self.assertFalse(PermisoAcceso.objects.exists())
        evento = EventoAcceso.objects.get()
        self.assertEqual((evento.persona, evento.identificador_biometrico_externo), (None, self.ident))

        orden = self.lector().get('/api/accesos/lector/bajas/siguiente/').json()
        self.assertEqual((orden['identificador'], orden['nombre']), (self.ident, 'Juan Pérez'))
        url = f'/api/accesos/lector/bajas/{orden["id"]}/resultado/'
        self.assertEqual(self.lector().post(url, {'exito': True, 'mensaje': 'borrada'}, format='json').status_code, 204)
        self.assertEqual(BajaHuella.objects.get().estado, 'Completada')
        self.assertEqual(self.lector().get('/api/accesos/lector/bajas/siguiente/').status_code, 204)

    def test_solo_contratistas_o_administrador(self):
        self.assertEqual(self.auditor.delete(f'/api/accesos/personas/{self.persona["id"]}/').status_code, 403)
        self.assertEqual(cliente_con_rol('tec', 'Tecnico').delete(f'/api/accesos/personas/{self.persona["id"]}/').status_code, 403)
        self.assertEqual(self.admin.delete(f'/api/accesos/personas/{self.persona["id"]}/').status_code, 200)



class RegistroDeAccesosPorRolTests(AccesosTestCase):
    def test_el_tecnico_no_ve_el_registro_de_accesos(self):
        self.assertEqual(cliente_con_rol('tec', 'Tecnico').get('/api/accesos/eventos/').status_code, 403)
        for usuario, rol in (('jefe', 'Jefatura'), ('aud2', 'Auditor')):
            self.assertEqual(cliente_con_rol(usuario, rol).get('/api/accesos/eventos/').status_code, 200)
