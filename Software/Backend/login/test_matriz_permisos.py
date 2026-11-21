"""Matriz de permisos de SICMA: recorre TODAS las rutas de la API con TODOS los roles.

    python manage.py test login.test_matriz_permisos -v 2

Para guardar la tabla rol x ruta x método como evidencia (CSV, separado por ";"):

    SICMA_MATRIZ_CSV=matriz_permisos.csv python manage.py test login.test_matriz_permisos

Qué se comprueba, con un JWT real de cada rol (el mismo que emite el login):
  - rol permitido      -> pasa el control de permisos (no recibe 401, 403 ni 405). Un 400 por
                          cuerpo vacío o un 404 por un id inexistente significan que SÍ pasó.
  - rol no permitido   -> 403.
  - sin token          -> 401.
  - token de la app    -> toda escritura recibe 403 (RF-PLT-02), salvo cerrar sesión y
    móvil                 registrar actividad.

Las rutas con parámetros se piden con un id que no existe: el permiso se evalúa antes de buscar
el objeto, así que un rol sin permiso recibe 403 y uno con permiso, 404. Las escrituras van con
cuerpo vacío, así que no modifican nada.

La matriz esperada está escrita aquí a mano a partir de la matriz de permisos del proyecto, sin
importar las constantes de login/permissions.py: si alguien cambia los roles de una vista, esta
prueba lo detecta. Si se agrega una ruta nueva sin declararla aquí, test_todas_las_rutas_estan_declaradas
falla. Lo que depende de los datos (el técnico solo ve sus intervenciones, el Administrador común no
edita cuentas de administración) lo cubren las pruebas de cada módulo.
"""
import csv
import os

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from .authentication import CLAIM_SOLO_LECTURA
from .serializers import EmailTokenObtainPairSerializer

# ----------------------------------------------------------------------------- roles
# Rol de SICMA -> grupo de Django que lo asigna.
GRUPOS = {
    'administradorprivilegiado': 'AdministradorPrivilegiado',
    'administrador': 'Administrador',
    'jefatura': 'Jefatura',
    'tecnico': 'Tecnico',
    'auditor': 'Auditor',
    'contratistas': 'Contratistas',
}

PRIV = {'administradorprivilegiado'}
ADMIN = PRIV | {'administrador'}
LECTURA = ADMIN | {'jefatura', 'tecnico', 'auditor'}         # consultan el monitoreo
TODOS = LECTURA | {'contratistas'}
GESTION_ALERTAS = ADMIN | {'tecnico'}                         # reconocen y cierran alertas
EDICION_ACTIVOS = ADMIN | {'tecnico'}                         # HU-04: el técnico registra activos
CONTRATISTAS = ADMIN | {'contratistas'}                       # enrolan y habilitan personal externo
REGISTRO_ACCESOS = ADMIN | {'jefatura', 'auditor'}            # RF-ACC-03: no lo ve el técnico
EJECUCION = ADMIN | {'tecnico'}                               # inician y cierran intervenciones
CANCELACION = ADMIN | {'jefatura'}

# ----------------------------------------------------------------------------- matriz esperada
# nombre de la ruta (urls.py) -> método -> roles que pueden usarlo.
MATRIZ = {
    # Cuenta propia: cualquier usuario con sesión.
    'current_user': {'GET': TODOS},
    'activity': {'POST': TODOS},
    'logout': {'POST': TODOS},
    # Usuarios: administración. La política de contraseñas y los tiempos de sesión los cambia
    # solo el Administrador Privilegiado (el Administrador común puede consultar la política).
    'password_policy': {'GET': ADMIN, 'PATCH': PRIV},
    'managed_user_list': {'GET': ADMIN, 'POST': ADMIN},
    'managed_user_detail': {'PATCH': ADMIN},
    'user_session_timeout': {'PATCH': PRIV},
    'usuario_mfa': {'POST': PRIV},  # exigir, restablecer o quitar la verificación en dos pasos
    # Sesiones activas: ambos administradores las ven y las revocan.
    'sesiones_lista': {'GET': ADMIN},
    'sesiones_revocar': {'POST': ADMIN},
    # Monitoreo ambiental.
    'medicion_ingest': {'GET': LECTURA},  # el POST es de los ESP32: ver EXCLUIDAS
    'sensor_list': {'GET': LECTURA, 'POST': ADMIN},
    'sensor_detail': {'GET': LECTURA, 'PATCH': ADMIN},
    'sensor_clave': {'POST': ADMIN},
    'sensor_historial': {'GET': LECTURA},
    'ubicacion_list': {'GET': LECTURA, 'POST': ADMIN},
    'ubicacion_detail': {'GET': LECTURA, 'PATCH': ADMIN},
    'umbral_list': {'GET': LECTURA, 'POST': ADMIN},
    # Inventario.
    'activo_list': {'GET': LECTURA, 'POST': EDICION_ACTIVOS},
    'activo_detail': {'GET': LECTURA, 'PATCH': EDICION_ACTIVOS},
    'activo_historial': {'GET': LECTURA},
    'activo_responsables': {'GET': LECTURA},
    'tipo_activo_list': {'GET': LECTURA, 'POST': ADMIN},
    'tipo_activo_detail': {'PATCH': ADMIN},
    'estado_activo_list': {'GET': LECTURA, 'POST': ADMIN},
    'estado_activo_detail': {'PATCH': ADMIN},
    # Infraestructura (Zabbix).
    'infraestructura_activos': {'GET': LECTURA},
    'infraestructura_estado': {'GET': LECTURA},
    'infraestructura_hosts': {'GET': LECTURA},
    'infraestructura_sincronizacion': {'GET': LECTURA},
    'infraestructura_eventos_host': {'GET': LECTURA},
    # Alertas.
    'alerta_list': {'GET': LECTURA},
    'alerta_reconocer': {'POST': GESTION_ALERTAS},
    'alerta_cerrar': {'POST': GESTION_ALERTAS},
    'alerta_responsables': {'GET': LECTURA},
    'alerta_responsables_zona': {'PUT': ADMIN},
    # Intervenciones.
    'intervencion_list': {'GET': LECTURA},
    'intervencion_tecnicos': {'GET': LECTURA},
    'intervencion_detail': {'GET': LECTURA},
    'intervencion_asignar': {'POST': ADMIN},
    'intervencion_personal': {'POST': ADMIN},
    'intervencion_verificar': {'POST': EJECUCION},
    'intervencion_iniciar': {'POST': EJECUCION},
    'intervencion_cerrar': {'POST': EJECUCION},
    'intervencion_cancelar': {'POST': CANCELACION},
    # Control de acceso físico.
    'acceso_eventos': {'GET': REGISTRO_ACCESOS},
    'acceso_verificacion': {'GET': LECTURA},
    'acceso_personas': {'GET': TODOS, 'POST': CONTRATISTAS},
    'acceso_persona': {'GET': TODOS, 'PATCH': CONTRATISTAS, 'DELETE': CONTRATISTAS},
    'acceso_persona_habilitacion': {'GET': TODOS, 'POST': CONTRATISTAS},
    'acceso_persona_enrolar': {'POST': CONTRATISTAS},
    'acceso_enrolamiento': {'GET': CONTRATISTAS},
    'acceso_enrolamiento_cancelar': {'POST': CONTRATISTAS},
    'acceso_puntos': {'GET': TODOS, 'POST': ADMIN},
    'acceso_punto': {'GET': LECTURA, 'PATCH': ADMIN},
    'acceso_punto_clave': {'POST': ADMIN},
    'acceso_permisos': {'GET': LECTURA, 'POST': ADMIN},
    'acceso_permiso': {'GET': LECTURA, 'PATCH': ADMIN},
    # Reportes.
    'reportes_resumen': {'GET': LECTURA},
    'reportes_pdf': {'GET': LECTURA},
    # Integraciones: estado y pruebas para la administración; renovar secretos, solo el privilegiado.
    'integraciones_estado': {'GET': ADMIN},
    'integraciones_probar': {'POST': ADMIN},
    'integraciones_renovar': {'POST': PRIV},
}

# Públicas a propósito: se usan antes de tener sesión. Sin token no deben responder 401/403.
PUBLICAS = {
    'token_obtain_pair': 'login',
    'token_refresh': 'renueva el token con el refresh token',
    'token_dispositivo': 'app móvil: entra con huella o PIN canjeando la llave del dispositivo',
    'token_mfa': 'segundo paso del login: código de la app de autenticación',
    'password_reset': 'pide el correo de recuperación',
    'password_reset_confirm': 'fija la contraseña nueva con el enlace del correo',
    'password_change': 'cambio de contraseña vencida antes de iniciar sesión (pide la actual)',
}

# Fuera de la matriz de roles: no las usa una persona, sino un dispositivo o un sistema.
EXCLUIDAS = {
    'medicion_ingest:POST': 'ESP32: clave del dispositivo (X-Device-Key), no rol',
    'zabbix_webhook': 'Zabbix: secreto compartido; además bloqueada desde internet en Cloudflare',
    'acceso_lector_intento': 'Agente del lector: punto de acceso y clave del dispositivo',
    'acceso_lector_verificacion': 'Agente del lector',
    'acceso_lector_verificacion_progreso': 'Agente del lector',
    'acceso_lector_verificacion_resultado': 'Agente del lector',
    'acceso_lector_baja': 'Agente del lector',
    'acceso_lector_baja_resultado': 'Agente del lector',
    'acceso_lector_enrolamiento': 'Agente del lector',
    'acceso_lector_enrolamiento_progreso': 'Agente del lector',
    'acceso_lector_enrolamiento_resultado': 'Agente del lector',
}

# Escrituras que el token de la app móvil sí puede hacer: mantener y cerrar su sesión.
ESCRITURAS_MOVIL_PERMITIDAS = {'activity', 'logout'}

METODOS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')
ESCRITURA = {'POST', 'PUT', 'PATCH', 'DELETE'}
ID_INEXISTENTE = 987654


def rutas_api():
    """{nombre: (patrón, {métodos}, {parámetros})} de todas las rutas bajo api/."""
    rutas = {}

    def recorrer(patrones, prefijo=''):
        for p in patrones:
            if isinstance(p, URLResolver):
                recorrer(p.url_patterns, prefijo + str(p.pattern))
            elif isinstance(p, URLPattern) and p.name:
                patron = prefijo + str(p.pattern)
                vista = getattr(p.callback, 'view_class', None) or getattr(p.callback, 'cls', None)
                if patron.startswith('api/') and vista is not None:
                    metodos = {m for m in METODOS if hasattr(vista, m.lower())}
                    rutas[p.name] = (patron, metodos, set(p.pattern.regex.groupindex))

    recorrer(get_resolver().url_patterns)
    return rutas


def url_de(patron, parametros):
    """Arma la URL con un valor inexistente en cada parámetro (<int:pk> -> 987654, <str:nombre> -> x)."""
    import re
    url = re.sub(r'<int:\w+>', str(ID_INEXISTENTE), patron)
    url = re.sub(r'<(?:str:)?\w+>', 'no-existe', url)
    return '/' + url


@override_settings(
    # Que ninguna vista llame a servicios reales durante la prueba.
    ZABBIX_URL='', ZABBIX_TOKEN='', GEMINI_API_KEY='', URL_PUBLICA_API='http://127.0.0.1:9/api',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class MatrizPermisosTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # Las tablas managed=False (en producción las crea el script SQL) se crean para la prueba.
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

    @classmethod
    def setUpTestData(cls):
        cls.tokens, cls.tokens_movil = {}, {}
        for rol, grupo in GRUPOS.items():
            usuario = get_user_model().objects.create_user(
                username=f'matriz_{rol}', email=f'{rol}@matriz.test', password='Clave-de-prueba-123!',
            )
            usuario.groups.set([Group.objects.get_or_create(name=grupo)[0]])
            refresh = EmailTokenObtainPairSerializer.get_token(usuario)  # el mismo que emite el login
            cls.tokens[rol] = str(refresh.access_token)
            refresh[CLAIM_SOLO_LECTURA] = True                         # lo que agrega el login con canal=movil
            cls.tokens_movil[rol] = str(refresh.access_token)

    def pedir(self, metodo, url, token=None):
        cache.clear()  # que el límite de intentos no afecte el resultado
        cliente = APIClient()
        if token:
            cliente.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return getattr(cliente, metodo.lower())(url, data={}, format='json').status_code

    def test_todas_las_rutas_estan_declaradas(self):
        rutas = rutas_api()
        self.assertGreater(len(rutas), 50, 'No se encontraron las rutas de la API.')
        problemas = []
        for nombre, (patron, metodos, _) in sorted(rutas.items()):
            if nombre in PUBLICAS or nombre in EXCLUIDAS:
                continue
            if nombre not in MATRIZ:
                problemas.append(f'Ruta sin permisos declarados: {nombre} ({patron}) {sorted(metodos)}')
                continue
            declarados = set(MATRIZ[nombre]) | {m for m in metodos if f'{nombre}:{m}' in EXCLUIDAS}
            if metodos - declarados:
                problemas.append(f'{nombre}: métodos sin declarar {sorted(metodos - declarados)}')
            if declarados - metodos:
                problemas.append(f'{nombre}: la matriz declara métodos que la vista no tiene {sorted(declarados - metodos)}')
        conocidas = set(MATRIZ) | set(PUBLICAS) | {n.split(':')[0] for n in EXCLUIDAS}
        problemas += [f'{n}: está en la matriz pero ya no existe' for n in sorted(conocidas - set(rutas))]
        self.assertFalse(problemas, '\n' + '\n'.join(problemas))

    def test_matriz_completa(self):
        rutas = rutas_api()
        filas, fallas = [], []

        def registrar(nombre, patron, metodo, quien, esperado, codigo, ok):
            filas.append([nombre, '/' + patron, metodo, quien, esperado, codigo, 'OK' if ok else 'FALLA'])
            if not ok:
                fallas.append(f'{metodo:6} {nombre:38} {quien:34} esperado={esperado:10} obtenido={codigo}')

        for nombre, (patron, metodos, parametros) in sorted(rutas.items()):
            url = url_de(patron, parametros)
            if nombre in PUBLICAS:
                for metodo in sorted(metodos):
                    codigo = self.pedir(metodo, url)
                    registrar(nombre, patron, metodo, 'sin sesión', 'pública', codigo, codigo not in (401, 403))
                continue
            for metodo in sorted(metodos):
                if nombre in EXCLUIDAS or f'{nombre}:{metodo}' in EXCLUIDAS:
                    motivo = EXCLUIDAS.get(nombre) or EXCLUIDAS[f'{nombre}:{metodo}']
                    filas.append([nombre, '/' + patron, metodo, '-', 'excluida', '-', motivo])
                    continue
                if nombre not in MATRIZ or metodo not in MATRIZ[nombre]:
                    continue  # lo informa test_todas_las_rutas_estan_declaradas
                permitidos = MATRIZ[nombre][metodo]

                codigo = self.pedir(metodo, url)
                registrar(nombre, patron, metodo, 'sin sesión', '401', codigo, codigo == 401)

                for rol in GRUPOS:
                    codigo = self.pedir(metodo, url, self.tokens[rol])
                    if rol in permitidos:
                        registrar(nombre, patron, metodo, rol, 'permitido', codigo, codigo not in (401, 403, 405))
                    else:
                        registrar(nombre, patron, metodo, rol, '403', codigo, codigo == 403)

                    # App móvil: solo consulta, sea cual sea el rol (RF-PLT-02).
                    if metodo in ESCRITURA and rol in permitidos:
                        codigo = self.pedir(metodo, url, self.tokens_movil[rol])
                        if nombre in ESCRITURAS_MOVIL_PERMITIDAS:
                            registrar(nombre, patron, metodo, f'{rol} (app móvil)', 'permitido', codigo,
                                      codigo not in (401, 403, 405))
                        else:
                            registrar(nombre, patron, metodo, f'{rol} (app móvil)', '403', codigo, codigo == 403)

        destino = os.environ.get('SICMA_MATRIZ_CSV')
        if destino:
            with open(destino, 'w', newline='', encoding='utf-8-sig') as archivo:
                escritor = csv.writer(archivo, delimiter=';')
                escritor.writerow(['ruta', 'patron', 'metodo', 'quien', 'esperado', 'obtenido', 'resultado'])
                escritor.writerows(filas)

        casos = sum(1 for f in filas if f[-1] in ('OK', 'FALLA'))
        print(f'\nMatriz de permisos: {casos - len(fallas)}/{casos} casos OK'
              + (f' -> {os.path.abspath(destino)}' if destino else ''))
        self.assertFalse(fallas, f'\n{len(fallas)} casos no cumplen la matriz:\n' + '\n'.join(fallas))
