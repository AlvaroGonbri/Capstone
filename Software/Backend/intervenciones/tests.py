import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accesos.models import EventoAcceso, PermisoAcceso, PermisoDia, PersonaAutorizada, PuntoAcceso
from alertas.models import Alerta, HostProblemaZabbix, Notificacion
from inventario.models import Activo
from mediciones.models import Ubicacion
from mediciones.tests import TablasNoGestionadasTestCase, cliente_con_rol

from .buzon import MensajeInvalido, extraer_json, leer_buzon, procesar_mensaje
from .models import DecisionIntervencion, Intervencion, IntervencionActivo, IntervencionPersona


User = get_user_model()
FLUJO = 'flujo@duocuc.cl'
TOKEN = 'secreto-del-flujo'


def correo_nueva(forms_id='R-1', **extra):
    return json.dumps({
        'tipo': 'nueva', 'token': TOKEN, 'forms_id': forms_id, 'correo': 'keyuser@duocuc.cl',
        'nombre': 'Key User', 'rack': 'Rack A1', 'fecha': '2026-10-20', 'hora': '14:30',
        'servicios': 'Correo, VPN', **extra,
    })


def correo_decision(decision='Approve', forms_id='R-1', **extra):
    return json.dumps({
        'tipo': 'decision', 'token': TOKEN, 'forms_id': forms_id, 'decision': decision,
        'decisor': 'jefe@duocuc.cl', 'comentario': 'OK', **extra,
    })


@override_settings(
    INTERVENCIONES_CORREO_FLUJO=FLUJO,
    INTERVENCIONES_TOKEN=TOKEN,
    ALERTAS_CORREO_ASINCRONO=False,
    DEFAULT_FROM_EMAIL='sicma@sicma.test',
)
class IntervencionesTestCase(TablasNoGestionadasTestCase):
    modelos = TablasNoGestionadasTestCase.modelos + (
        Activo, HostProblemaZabbix, Alerta, Notificacion, Intervencion, DecisionIntervencion, IntervencionActivo,
        PersonaAutorizada, PuntoAcceso, PermisoAcceso, PermisoDia, EventoAcceso,
    )

    def setUp(self):
        self.admin = cliente_con_rol('admin', 'Administrador')
        self.auditor = cliente_con_rol('auditor', 'Auditor')
        self.tecnico_cliente = cliente_con_rol('tecnico', 'Tecnico')
        self.tecnico = User.objects.get(username='tecnico')
        self.tecnico.email = 'tecnico@sicma.test'
        self.tecnico.save()

    def recibir(self, cuerpo, remitente=FLUJO, asunto='[SICMA-INT] NUEVA'):
        with self.captureOnCommitCallbacks(execute=True):
            return procesar_mensaje(f'Flujo SICMA <{remitente}>', asunto, cuerpo)

    def aprobada(self):
        self.recibir(correo_nueva())
        self.recibir(correo_decision(), asunto='[SICMA-INT] DECISION')
        mail.outbox.clear()
        return Intervencion.objects.get(origen_externo_id='R-1')

    def asignar(self, intervencion, **extra):
        inicio = timezone.now() + timedelta(days=1)
        with self.captureOnCommitCallbacks(execute=True):
            return self.admin.post(f'/api/intervenciones/{intervencion.id}/asignar/', {
                'tecnico': self.tecnico.id, 'fecha_inicio': inicio.isoformat(),
                'fecha_termino': (inicio + timedelta(hours=2)).isoformat(), **extra,
            }, format='json')


class BuzonTests(IntervencionesTestCase):
    def test_solicitud_de_forms_crea_la_intervencion_pendiente_y_avisa_al_solicitante(self):
        resultado = self.recibir(correo_nueva())

        intervencion = Intervencion.objects.get(pk=resultado.intervencion_id)
        self.assertEqual((intervencion.estado, intervencion.rack, intervencion.impacto_esperado), ('Pendiente', 'Rack A1', 'Correo, VPN'))
        # 14:30 en Santiago (UTC-3 en octubre) = 17:30 UTC.
        self.assertEqual(intervencion.fecha_inicio, datetime(2026, 10, 20, 17, 30, tzinfo=ZoneInfo('UTC')))
        self.assertEqual([m.to for m in mail.outbox], [['keyuser@duocuc.cl']])
        self.assertIn('pendiente de aprobación', mail.outbox[0].subject)

    def test_hora_de_termino_opcional_y_cruce_de_medianoche(self):
        self.recibir(correo_nueva('R-1', hora_termino='16:00'))
        self.recibir(correo_nueva('R-2', hora='23:00', hora_termino='02:00'))
        utc = ZoneInfo('UTC')
        self.assertEqual(Intervencion.objects.get(origen_externo_id='R-1').fecha_termino, datetime(2026, 10, 20, 19, 0, tzinfo=utc))
        self.assertEqual(Intervencion.objects.get(origen_externo_id='R-2').fecha_termino, datetime(2026, 10, 21, 5, 0, tzinfo=utc))
        self.recibir(correo_nueva('R-3', hora_termino=None))
        self.assertIsNone(Intervencion.objects.get(origen_externo_id='R-3').fecha_termino)

    def test_descripcion_y_plan_de_reversa_del_formulario(self):
        self.recibir(correo_nueva(descripcion='Cambio de fuente', plan_reversa='Volver a la fuente original'))
        intervencion = Intervencion.objects.get()
        self.assertEqual((intervencion.descripcion, intervencion.plan_reversa), ('Cambio de fuente', 'Volver a la fuente original'))
        self.assertIn('Cambio de fuente', mail.outbox[0].body)

    def test_el_mismo_correo_dos_veces_no_duplica(self):
        self.recibir(correo_nueva())
        repetido = self.recibir(correo_nueva())
        self.assertFalse(repetido.nueva)
        self.assertEqual((Intervencion.objects.count(), len(mail.outbox)), (1, 1))

    def test_rechaza_remitente_token_asunto_o_datos_invalidos(self):
        casos = [
            (correo_nueva(), 'otro@duocuc.cl', '[SICMA-INT] NUEVA'),
            (correo_nueva(token='malo'), FLUJO, '[SICMA-INT] NUEVA'),
            (correo_nueva(), FLUJO, 'Hola'),
            (correo_nueva(fecha='mañana'), FLUJO, '[SICMA-INT] NUEVA'),
            ('sin json', FLUJO, '[SICMA-INT] NUEVA'),
        ]
        for cuerpo, remitente, asunto in casos:
            with self.subTest(remitente=remitente, asunto=asunto, cuerpo=cuerpo[:30]):
                with self.assertRaises(MensajeInvalido):
                    self.recibir(cuerpo, remitente, asunto)
        self.assertEqual(Intervencion.objects.count(), 0)

    def test_json_dentro_de_html_de_outlook(self):
        html = '<html><body><p>{&quot;tipo&quot;: &quot;nueva&quot;,</p><p>&quot;rack&quot;: &quot;R&quot;}</p></body></html>'
        self.assertEqual(extraer_json(html), {'tipo': 'nueva', 'rack': 'R'})

    def test_json_cortado_por_outlook_con_saltos_y_comillas_tipograficas(self):
        cuerpo = '{"tipo": "nueva", "token": "\r\nabc\r\ndef", “rack”:\xa0"R",\n"servicios": "a\\nb"}'
        self.assertEqual(extraer_json(cuerpo), {'tipo': 'nueva', 'token': 'abcdef', 'rack': 'R', 'servicios': 'a\nb'})

    def test_enlaces_y_estilos_de_outlook(self):
        # Texto plano: Outlook agrega el destino del enlace entre < > (caso real de la prueba manual).
        plano = '{"correo": "a <tu_correo@duocuc.cl>\r\nlv.gonzalezb@duocuc.cl", "rack": "A1"}'
        self.assertEqual(extraer_json(plano)['correo'], 'alv.gonzalezb@duocuc.cl')
        # HTML: hoja de estilos con llaves y el correo como enlace mailto.
        html = ('<html><head><style>p.MsoNormal {margin:0}</style></head><body><p>{&quot;correo&quot;: '
                '&quot;<a href="mailto:x@duocuc.cl">x@duocuc.cl</a>&quot;}</p></body></html>')
        self.assertEqual(extraer_json(html), {'correo': 'x@duocuc.cl'})

    def test_decision_de_la_jefatura_aprueba_o_rechaza_una_sola_vez(self):
        jefe = User.objects.create_user(username='jefe', email='JEFE@duocuc.cl', password='x')
        self.recibir(correo_nueva())
        self.recibir(correo_nueva('R-2'))

        self.recibir(correo_decision('Approve'), asunto='[SICMA-INT] DECISION')
        self.recibir(correo_decision('Rechazar', forms_id='R-2'), asunto='[SICMA-INT] DECISION')
        repetida = self.recibir(correo_decision('Reject'), asunto='[SICMA-INT] DECISION')

        self.assertFalse(repetida.nueva)
        self.assertEqual(Intervencion.objects.get(origen_externo_id='R-1').estado, 'Aprobada')
        self.assertEqual(Intervencion.objects.get(origen_externo_id='R-2').estado, 'Rechazada')
        decision = DecisionIntervencion.objects.get(intervencion__origen_externo_id='R-1')
        self.assertEqual((decision.decisor, decision.decisor_correo, decision.decision), (jefe, 'jefe@duocuc.cl', 'Aprobada'))
        with self.assertRaises(MensajeInvalido):
            self.recibir(correo_decision(forms_id='NO-EXISTE'), asunto='[SICMA-INT] DECISION')

    def test_decision_sin_comentario_llega_como_null(self):
        self.recibir(correo_nueva(servicios=None))
        self.recibir(correo_decision(comentario=None), asunto='[SICMA-INT] DECISION')
        self.assertEqual(DecisionIntervencion.objects.get().observacion, None)

    def test_leer_buzon_marca_leidos_solo_los_procesados_o_descartados(self):
        imap = MagicMock()
        imap.__enter__.return_value = imap
        imap.search.return_value = ('OK', [b'1 2'])
        crudos = {
            b'1': f'From: {FLUJO}\r\nSubject: [SICMA-INT] NUEVA\r\n\r\n{correo_nueva()}'.encode(),
            b'2': f'From: intruso@x.cl\r\nSubject: [SICMA-INT] NUEVA\r\n\r\n{correo_nueva("R-9")}'.encode(),
        }
        imap.fetch.side_effect = lambda numero, _: ('OK', [(b'', crudos[numero])])

        with override_settings(EMAIL_HOST_USER='sicma@gmail.com', EMAIL_HOST_PASSWORD='x'), \
                patch('intervenciones.buzon.imaplib.IMAP4_SSL', return_value=imap), \
                self.captureOnCommitCallbacks(execute=True):
            procesados, descartados = leer_buzon()

        self.assertEqual((len(procesados), len(descartados)), (1, 1))
        self.assertEqual(sorted(c.args[0] for c in imap.store.call_args_list), [b'1', b'2'])
        self.assertEqual(Intervencion.objects.get().origen_externo_id, 'R-1')


class CicloDeVidaTests(IntervencionesTestCase):
    def test_asignar_pide_agendar_al_flujo_y_avisa_al_tecnico(self):
        intervencion = self.aprobada()
        sala = Ubicacion.objects.create(sala='Sala A')
        activo = Activo.objects.create(codigo='mysql01', nombre='Nodo 01', numero_serie='SN', ubicacion=sala, fecha_alta=timezone.now())

        respuesta = self.asignar(intervencion, activos=[activo.id])

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual((datos['responsable'], datos['activos'][0]['codigo']), (self.tecnico.id, 'mysql01'))
        agenda = next(m for m in mail.outbox if m.to == [FLUJO])
        self.assertEqual(agenda.subject, f'[SICMA-INT] AGENDAR #{intervencion.id}')
        cuerpo = json.loads(agenda.body)
        self.assertEqual((cuerpo['tecnico_correo'], cuerpo['rack']), ('tecnico@sicma.test', 'Rack A1'))
        self.assertTrue(self.auditor.get(f'/api/intervenciones/{intervencion.id}/').json()['agenda_enviada'])
        avisados = sorted(m.to[0] for m in mail.outbox if m.to != [FLUJO])
        self.assertEqual(avisados, ['keyuser@duocuc.cl', 'tecnico@sicma.test'])
        self.assertEqual(self.auditor.get('/api/intervenciones/', {'activo': activo.id}).json()[0]['id'], intervencion.id)

    def test_tecnico_inicia_y_cierra_su_intervencion(self):
        intervencion = self.aprobada()
        otro = cliente_con_rol('otro', 'Tecnico')
        url = f'/api/intervenciones/{intervencion.id}/'

        self.assertEqual(self.admin.post(url + 'iniciar/').status_code, 409)  # sin técnico asignado
        self.asignar(intervencion)
        self.assertEqual(otro.post(url + 'iniciar/').status_code, 403)
        self.assertEqual(self.tecnico_cliente.post(url + 'iniciar/').json()['estado'], 'EnEjecucion')
        self.assertEqual(self.tecnico_cliente.post(url + 'cerrar/', {'exitosa': True}, format='json').status_code, 400)

        cerrada = self.tecnico_cliente.post(url + 'cerrar/', {'exitosa': False, 'observacion': 'Falló el switch'}, format='json').json()
        self.assertEqual((cerrada['estado'], cerrada['observacion_cierre']), ('Fallida', 'Falló el switch'))
        self.assertIsNotNone(cerrada['fecha_cierre'])

    def test_reglas_de_estado_y_permisos(self):
        self.recibir(correo_nueva())
        pendiente = Intervencion.objects.get()
        url = f'/api/intervenciones/{pendiente.id}/'

        self.assertEqual(self.asignar(pendiente).status_code, 409)  # aún no la aprueba la Jefatura
        self.assertEqual(self.tecnico_cliente.post(url + 'cancelar/', {'motivo': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.auditor.post(url + 'asignar/', {}, format='json').status_code, 403)
        self.assertEqual(self.admin.post(url + 'cancelar/', {'motivo': 'Duplicada'}, format='json').json()['estado'], 'Cancelada')
        self.assertEqual(self.admin.post(url + 'cancelar/', {'motivo': 'otra vez'}, format='json').status_code, 409)
        self.assertEqual([i['id'] for i in self.auditor.get('/api/intervenciones/', {'estado': 'Cancelada'}).json()], [pendiente.id])

    def test_solo_se_asigna_a_tecnicos_o_administradores_y_con_horario_valido(self):
        intervencion = self.aprobada()
        auditor = User.objects.get(username='auditor')
        self.assertIn('tecnico', self.asignar(intervencion, tecnico=auditor.id).json())
        inicio = timezone.now()
        respuesta = self.admin.post(f'/api/intervenciones/{intervencion.id}/asignar/', {
            'tecnico': self.tecnico.id, 'fecha_inicio': inicio.isoformat(), 'fecha_termino': inicio.isoformat(),
        }, format='json')
        self.assertIn('fecha_termino', respuesta.json())
        tecnicos = [t['id'] for t in self.auditor.get('/api/intervenciones/tecnicos/').json()]
        self.assertIn(self.tecnico.id, tecnicos)
        self.assertNotIn(auditor.id, tecnicos)


class PersonalExternoTests(IntervencionesTestCase):
    def setUp(self):
        super().setUp()
        self.juan = PersonaAutorizada.objects.create(
            nombre='Juan Pérez', identificador_biometrico_externo='EXT-00001', empresa='Clima Ltda.',
            rut='12345678-5', huella_registrada_en=timezone.now(),
        )
        self.sin_huella = PersonaAutorizada.objects.create(nombre='Ana Soto', identificador_biometrico_externo='EXT-00002')
        self.deshabilitado = PersonaAutorizada.objects.create(
            nombre='Luis Mora', identificador_biometrico_externo='EXT-00003', estado='Inactivo', huella_registrada_en=timezone.now(),
        )

    def test_asignar_con_personal_externo_lo_muestra_y_lo_informa(self):
        intervencion = self.aprobada()
        respuesta = self.asignar(intervencion, personal_externo=[self.juan.id])
        self.assertEqual(respuesta.status_code, 200)
        personal = respuesta.json()['personal_externo']
        self.assertEqual([(p['nombre'], p['empresa'], p['habilitada'], p['huella_registrada']) for p in personal],
                         [('Juan Pérez', 'Clima Ltda.', True, True)])
        agenda = next(m for m in mail.outbox if m.to == [FLUJO])
        self.assertIn('Personal externo: Juan Pérez (Clima Ltda.)', json.loads(agenda.body)['detalle'])
        self.assertTrue(any('Personal externo: Juan Pérez' in m.body for m in mail.outbox if m.to != [FLUJO]))

    def test_solo_personal_habilitado_y_con_huella(self):
        intervencion = self.aprobada()
        error = self.asignar(intervencion, personal_externo=[self.sin_huella.id, self.deshabilitado.id]).json()
        self.assertIn('Ana Soto: no tiene huella registrada', error['personal_externo'][0])
        self.assertIn('Luis Mora: está deshabilitada', error['personal_externo'][0])

    def test_cambiar_solo_el_personal_hasta_que_se_inicia(self):
        intervencion = self.aprobada()
        self.asignar(intervencion)
        mail.outbox.clear()
        url = f'/api/intervenciones/{intervencion.id}/personal/'
        self.assertEqual(self.admin.post(url, {'personal_externo': [self.juan.id]}, format='json').json()['personal_externo'][0]['id'], self.juan.id)
        self.assertFalse(any(m.to == [FLUJO] for m in mail.outbox))  # no vuelve a pedir la cita
        self.assertEqual(self.tecnico_cliente.post(url, {'personal_externo': []}, format='json').status_code, 403)

        # Parte 3: para iniciar, el personal externo debe haber verificado su huella.
        IntervencionPersona.objects.filter(intervencion=intervencion).update(verificada_en=timezone.now())
        self.assertEqual(self.tecnico_cliente.post(f'/api/intervenciones/{intervencion.id}/iniciar/').status_code, 200)
        self.assertEqual(self.admin.post(url, {'personal_externo': []}, format='json').status_code, 409)

    def test_si_se_deshabilita_despues_la_intervencion_lo_advierte(self):
        intervencion = self.aprobada()
        self.asignar(intervencion, personal_externo=[self.juan.id])
        PersonaAutorizada.objects.filter(pk=self.juan.id).update(estado='Inactivo')
        persona = self.auditor.get(f'/api/intervenciones/{intervencion.id}/').json()['personal_externo'][0]
        self.assertFalse(persona['habilitada'])


class VerificacionDeIdentidadTests(IntervencionesTestCase):
    """Parte 3: permiso automático para la ventana y verificación por huella antes de iniciar."""

    def setUp(self):
        from django.contrib.auth.hashers import make_password

        super().setUp()
        self.sala = Ubicacion.objects.create(sala='Sala A')
        self.punto = PuntoAcceso.objects.create(nombre='Puerta', ubicacion=self.sala, device_key_hash=make_password('clave'))
        self.juan = PersonaAutorizada.objects.create(
            nombre='Juan Pérez', identificador_biometrico_externo='EXT-00001', empresa='Clima', huella_registrada_en=timezone.now(),
        )
        self.intervencion = self.aprobada()
        ahora = timezone.now()
        self.asignar(self.intervencion, personal_externo=[self.juan.id],
                     fecha_inicio=(ahora - timedelta(minutes=10)).isoformat(), fecha_termino=(ahora + timedelta(hours=2)).isoformat())
        self.base = f'/api/intervenciones/{self.intervencion.id}/'

    def lector(self):
        cliente = APIClient()
        cliente.credentials(HTTP_X_PUNTO_ACCESO=str(self.punto.id), HTTP_X_DEVICE_KEY='clave')
        return cliente

    def verificar(self, coincide=True, identificado='EXT-00001', mensaje='Identidad verificada.'):
        solicitud = self.tecnico_cliente.post(self.base + f'personal/{self.juan.id}/verificar/', {}, format='json').json()
        trabajo = self.lector().get('/api/accesos/lector/verificaciones/siguiente/').json()
        self.assertEqual((trabajo['id'], trabajo['identificador']), (solicitud['id'], 'EXT-00001'))
        self.lector().post(f'/api/accesos/lector/verificaciones/{solicitud["id"]}/resultado/',
                           {'coincide': coincide, 'identificado': identificado, 'mensaje': mensaje}, format='json')
        return solicitud

    def test_asignar_crea_un_permiso_solo_para_la_ventana_y_cerrar_lo_revoca(self):
        permiso = PermisoAcceso.objects.get(persona=self.juan)
        self.assertEqual(permiso.estado, 'Activo')
        hoy = timezone.localtime(timezone.now(), ZoneInfo('America/Santiago')).date()
        self.assertTrue(permiso.vigencia_inicio <= hoy <= permiso.vigencia_fin)
        # En el mismo día lleva su ventana horaria; si cruza la medianoche, vale los días completos.
        un_dia = permiso.vigencia_inicio == permiso.vigencia_fin
        self.assertEqual(PermisoDia.objects.filter(permiso=permiso).count(), 1 if un_dia else 0)
        self.admin.post(self.base + 'cancelar/', {'motivo': 'x'}, format='json')
        self.assertEqual(PermisoAcceso.objects.get(pk=permiso.pk).estado, 'Revocado')

    def test_quitar_a_la_persona_revoca_su_permiso(self):
        self.admin.post(self.base + 'personal/', {'personal_externo': []}, format='json')
        self.assertEqual(PermisoAcceso.objects.get(persona=self.juan).estado, 'Revocado')

    def test_no_se_inicia_sin_verificar_y_si_despues_de_verificar(self):
        respuesta = self.tecnico_cliente.post(self.base + 'iniciar/')
        self.assertEqual(respuesta.status_code, 409)
        self.assertIn('Juan Pérez (sin verificar su huella)', respuesta.json()['detail'])

        self.verificar()
        persona = self.auditor.get(self.base).json()['personal_externo'][0]
        self.assertIsNotNone(persona['verificada_en'])
        self.assertEqual(persona['verificacion']['estado'], 'Completada')
        evento = EventoAcceso.objects.get()
        self.assertEqual((evento.resultado, evento.persona), ('Permitido', self.juan))
        self.assertIn(f'intervención #{self.intervencion.id}', evento.motivo)
        self.assertEqual(self.tecnico_cliente.post(self.base + 'iniciar/').json()['estado'], 'EnEjecucion')

    def test_huella_de_otra_persona_queda_como_denegada(self):
        ana = PersonaAutorizada.objects.create(nombre='Ana', identificador_biometrico_externo='EXT-00009')
        self.verificar(coincide=False, identificado='EXT-00009', mensaje='La huella corresponde a otra persona (EXT-00009).')
        evento = EventoAcceso.objects.get()
        self.assertEqual((evento.resultado, evento.persona, evento.identificador_biometrico_externo), ('Denegado', ana, 'EXT-00009'))
        self.assertEqual(self.tecnico_cliente.post(self.base + 'iniciar/').status_code, 409)

    def test_deshabilitada_despues_de_verificar_no_deja_iniciar(self):
        self.verificar()
        PersonaAutorizada.objects.filter(pk=self.juan.id).update(estado='Inactivo')
        self.assertIn('(deshabilitada)', self.tecnico_cliente.post(self.base + 'iniciar/').json()['detail'])

    def test_fuera_de_la_ventana_no_se_puede_verificar(self):
        manana = timezone.now() + timedelta(days=1)
        self.asignar(self.intervencion, fecha_inicio=manana.isoformat(), fecha_termino=(manana + timedelta(hours=1)).isoformat())
        respuesta = self.tecnico_cliente.post(self.base + f'personal/{self.juan.id}/verificar/', {}, format='json')
        self.assertEqual(respuesta.status_code, 409)
        self.assertIn('desde 1 hora antes del inicio', respuesta.json()['detail'])

    def test_solo_el_tecnico_asignado_o_el_administrador(self):
        otro = cliente_con_rol('otro', 'Tecnico')
        self.assertEqual(otro.post(self.base + f'personal/{self.juan.id}/verificar/', {}, format='json').status_code, 403)
        self.assertEqual(self.auditor.post(self.base + f'personal/{self.juan.id}/verificar/', {}, format='json').status_code, 403)



class JefaturaCancelaTests(IntervencionesTestCase):
    def test_jefatura_puede_cancelar_y_el_tecnico_no(self):
        intervencion = self.aprobada()
        url = f'/api/intervenciones/{intervencion.id}/cancelar/'
        self.assertEqual(self.tecnico_cliente.post(url, {'motivo': 'x'}, format='json').status_code, 403)
        respuesta = cliente_con_rol('jefe', 'Jefatura').post(url, {'motivo': 'Se reprograma'}, format='json')
        self.assertEqual((respuesta.status_code, respuesta.json()['estado']), (200, 'Cancelada'))
