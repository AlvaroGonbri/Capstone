import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from alertas.models import Alerta, HostProblemaZabbix, Notificacion
from inventario.models import Activo
from mediciones.models import Ubicacion
from mediciones.tests import TablasNoGestionadasTestCase, cliente_con_rol

from .buzon import MensajeInvalido, extraer_json, leer_buzon, procesar_mensaje
from .models import DecisionIntervencion, Intervencion, IntervencionActivo


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
