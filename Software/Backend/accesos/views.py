import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from login.permissions import ADMIN_ROLES, CONTRATISTAS_ROLES, READ_ROLES, REGISTRO_ACCESOS_ROLES, RolePermission

from . import servicio
from .models import (
    ACTIVO,
    BAJA_PENDIENTE,
    ENROL_ABIERTAS,
    ENROL_CANCELADA,
    INACTIVO,
    EventoAcceso,
    PermisoAcceso,
    PersonaAutorizada,
    PuntoAcceso,
    BajaHuella,
    SolicitudEnrolamiento,
    SolicitudVerificacion,
)
from .serializers import (
    CambioHabilitacionSerializer,
    EventoFiltroSerializer,
    HabilitacionSerializer,
    ProgresoEnrolamientoSerializer,
    ProgresoVerificacionSerializer,
    ResultadoVerificacionSerializer,
    SolicitudVerificacionSerializer,
    ResultadoEnrolamientoSerializer,
    SolicitarEnrolamientoSerializer,
    SolicitudEnrolamientoSerializer,
    EventoSerializer,
    IntentoLectorSerializer,
    PermisoSerializer,
    PersonaSerializer,
    PuntoAccesoSerializer,
)


LIMITE_EVENTOS = 500


class LecturaTodosEscrituraAdminMixin:
    """Consultan todos los roles; mantiene personas, puntos y permisos el Administrador."""

    permission_classes = [RolePermission]

    @property
    def allowed_roles(self):
        return READ_ROLES if self.request.method == 'GET' else ADMIN_ROLES


class ListaCrearView(LecturaTodosEscrituraAdminMixin, APIView):
    serializer_class = None
    queryset = None

    def filtrar(self, request, queryset):
        return queryset

    def get(self, request, format=None):
        return Response(self.serializer_class(self.filtrar(request, self.queryset.all()), many=True).data)

    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self.serializer_class(serializer.save()).data, status=status.HTTP_201_CREATED)


class EditarView(LecturaTodosEscrituraAdminMixin, APIView):
    serializer_class = None
    queryset = None

    def get(self, request, pk, format=None):
        return Response(self.serializer_class(get_object_or_404(self.queryset, pk=pk)).data)

    def patch(self, request, pk, format=None):
        serializer = self.serializer_class(get_object_or_404(self.queryset, pk=pk), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(self.serializer_class(serializer.save()).data)


# El personal externo lo consultan todos los roles y el Departamento de contratistas; lo mantienen
# contratistas y el Administrador.
ROLES_LECTURA_PERSONAL = READ_ROLES + ('contratistas',)


class PersonalPermisosMixin:
    permission_classes = [RolePermission]

    @property
    def allowed_roles(self):
        return ROLES_LECTURA_PERSONAL if self.request.method == 'GET' else CONTRATISTAS_ROLES


def _personas():
    return PersonaAutorizada.objects.select_related('usuario', 'huella_registrada_por').prefetch_related(
        'enrolamientos__punto_acceso', 'enrolamientos__solicitada_por',
    )


class PersonaListView(PersonalPermisosMixin, ListaCrearView):
    """GET (?q= nombre, RUT, empresa o identificador; ?estado=) y POST personas. No se borran."""
    serializer_class = PersonaSerializer
    queryset = _personas().order_by('nombre')

    def filtrar(self, request, queryset):
        texto = request.query_params.get('q', '').strip()
        if texto:
            # El RUT se guarda como 12345678-5: también se encuentra si lo escriben con puntos.
            rut = texto.replace('.', '').upper()
            queryset = queryset.filter(
                Q(nombre__icontains=texto) | Q(empresa__icontains=texto)
                | Q(identificador_biometrico_externo__icontains=texto) | Q(rut__icontains=rut)
            )
        estado = request.query_params.get('estado')
        if estado in (ACTIVO, INACTIVO):
            queryset = queryset.filter(estado=estado)
        return queryset


class PersonaDetailView(PersonalPermisosMixin, EditarView):
    """GET, PATCH y DELETE de una persona. Borrarla ordena a los lectores borrar su huella."""
    serializer_class = PersonaSerializer
    queryset = _personas()

    def delete(self, request, pk, format=None):
        persona = get_object_or_404(PersonaAutorizada, pk=pk)
        lectores = servicio.eliminar_persona(persona, request.user)
        return Response({'lectores_notificados': lectores})


class PersonaHabilitacionView(PersonalPermisosMixin, APIView):
    """GET: historial de habilitación. POST: habilita o deshabilita (deshabilitar exige motivo)."""

    def get(self, request, pk, format=None):
        persona = get_object_or_404(PersonaAutorizada, pk=pk)
        cambios = persona.cambios_habilitacion.select_related('usuario')
        return Response(CambioHabilitacionSerializer(cambios, many=True).data)

    def post(self, request, pk, format=None):
        persona = get_object_or_404(PersonaAutorizada, pk=pk)
        serializer = HabilitacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        servicio.cambiar_habilitacion(persona, datos['habilitada'], datos['motivo'].strip(), request.user)
        return Response(PersonaSerializer(_personas().get(pk=pk)).data)


class PersonaEnrolarView(APIView):
    """POST: pide al agente del lector que capture la huella (la persona debe estar frente al lector)."""
    permission_classes = [RolePermission]
    allowed_roles = CONTRATISTAS_ROLES

    def post(self, request, pk, format=None):
        persona = get_object_or_404(PersonaAutorizada, pk=pk)
        serializer = SolicitarEnrolamientoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        punto = serializer.validated_data.get('punto_acceso')
        if punto is None:
            activos = list(PuntoAcceso.objects.filter(estado=ACTIVO)[:2])
            if len(activos) != 1:
                return Response({'punto_acceso': 'Elige en qué lector se enrolará la huella.'}, status=status.HTTP_400_BAD_REQUEST)
            punto = activos[0]
        solicitud = servicio.solicitar_enrolamiento(persona, punto, request.user)
        return Response(SolicitudEnrolamientoSerializer(solicitud).data, status=status.HTTP_201_CREATED)


class EnrolamientoDetailView(APIView):
    """GET: estado de una solicitud (la vista lo consulta mientras la persona apoya el dedo)."""
    permission_classes = [RolePermission]
    allowed_roles = CONTRATISTAS_ROLES

    def get(self, request, pk, format=None):
        solicitud = get_object_or_404(SolicitudEnrolamiento.objects.select_related('punto_acceso', 'solicitada_por'), pk=pk)
        return Response(SolicitudEnrolamientoSerializer(solicitud).data)


class EnrolamientoCancelarView(APIView):
    permission_classes = [RolePermission]
    allowed_roles = CONTRATISTAS_ROLES

    def post(self, request, pk, format=None):
        solicitud = get_object_or_404(SolicitudEnrolamiento.objects.select_related('punto_acceso', 'solicitada_por'), pk=pk)
        if solicitud.estado in ENROL_ABIERTAS:
            solicitud.estado, solicitud.mensaje = ENROL_CANCELADA, 'Cancelada desde SICMA.'
            solicitud.save(update_fields=['estado', 'mensaje'])
        return Response(SolicitudEnrolamientoSerializer(solicitud).data)


def _nueva_clave(punto):
    clave = secrets.token_urlsafe(32)
    punto.device_key_hash = make_password(clave)
    return clave


class PuntoListView(ListaCrearView):
    """GET/POST puntos de acceso. El alta entrega la clave del agente UNA sola vez."""

    @property
    def allowed_roles(self):
        # Contratistas los lista para elegir en qué lector enrolar.
        return ROLES_LECTURA_PERSONAL if self.request.method == 'GET' else ADMIN_ROLES

    serializer_class = PuntoAccesoSerializer
    queryset = PuntoAcceso.objects.select_related('ubicacion').order_by('nombre')

    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        punto = serializer.save()
        clave = _nueva_clave(punto)
        punto.save(update_fields=['device_key_hash'])
        return Response({**self.serializer_class(punto).data, 'clave_dispositivo': clave}, status=status.HTTP_201_CREATED)


class PuntoDetailView(EditarView):
    serializer_class = PuntoAccesoSerializer
    queryset = PuntoAcceso.objects.select_related('ubicacion')


class PuntoClaveView(APIView):
    """POST: genera una clave nueva para el agente; la anterior deja de funcionar de inmediato."""
    permission_classes = [RolePermission]
    allowed_roles = ADMIN_ROLES

    def post(self, request, pk, format=None):
        punto = get_object_or_404(PuntoAcceso, pk=pk)
        clave = _nueva_clave(punto)
        punto.save(update_fields=['device_key_hash'])
        return Response({'id': punto.id, 'nombre': punto.nombre, 'clave_dispositivo': clave})


class PermisoListView(ListaCrearView):
    """GET (?persona=, ?punto=) y POST permisos. Revocar = PATCH estado 'Revocado'."""
    serializer_class = PermisoSerializer
    queryset = PermisoAcceso.objects.select_related('persona', 'punto_acceso').prefetch_related('dias').order_by('-id')

    def filtrar(self, request, queryset):
        for parametro, campo in (('persona', 'persona_id'), ('punto', 'punto_acceso_id')):
            valor = request.query_params.get(parametro)
            if valor and valor.isdigit():
                queryset = queryset.filter(**{campo: int(valor)})
        return queryset


class PermisoDetailView(EditarView):
    serializer_class = PermisoSerializer
    queryset = PermisoAcceso.objects.select_related('persona', 'punto_acceso').prefetch_related('dias')


class EventoListView(APIView):
    """GET: registro de intentos de acceso, del más reciente al más antiguo (RF-ACC-03).

    Solo lectura: los eventos se crean únicamente desde el agente del lector y nunca se editan.
    Lo consultan Administración, Jefatura y Auditor; el Técnico no (información sensible).
    """
    permission_classes = [RolePermission]
    allowed_roles = REGISTRO_ACCESOS_ROLES

    def get(self, request, format=None):
        filtros = EventoFiltroSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        f = filtros.validated_data
        eventos = EventoAcceso.objects.select_related('persona', 'punto_acceso__ubicacion')
        if 'desde' in f:
            eventos = eventos.filter(fecha_hora__date__gte=f['desde'])
        if 'hasta' in f:
            eventos = eventos.filter(fecha_hora__date__lte=f['hasta'])
        if 'resultado' in f:
            eventos = eventos.filter(resultado=f['resultado'])
        if 'punto' in f:
            eventos = eventos.filter(punto_acceso_id=f['punto'])
        if 'persona' in f:
            eventos = eventos.filter(persona_id=f['persona'])
        if f.get('q'):
            eventos = eventos.filter(
                Q(persona__nombre__icontains=f['q']) | Q(identificador_biometrico_externo__icontains=f['q'])
            )
        return Response(EventoSerializer(eventos.order_by('-fecha_hora', '-id')[:LIMITE_EVENTOS], many=True).data)


def autenticar_lector(request):
    """El agente se identifica con X-Punto-Acceso + X-Device-Key (como los sensores). None si no es válido."""
    punto_id = request.headers.get('X-Punto-Acceso', '')
    clave = request.headers.get('X-Device-Key', '')
    punto = PuntoAcceso.objects.filter(pk=int(punto_id)).first() if punto_id.isdigit() else None
    if (punto is None or punto.estado != ACTIVO or not clave or not punto.device_key_hash
            or not check_password(clave, punto.device_key_hash)):
        return None
    return punto


def _lector_no_valido():
    return Response({'detail': 'Credenciales del lector no válidas.'}, status=status.HTTP_401_UNAUTHORIZED)


class LectorEnrolamientoSiguienteView(APIView):
    """GET del agente: la próxima huella que debe enrolar (204 si no hay ninguna)."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        solicitud = servicio.tomar_enrolamiento(punto)
        if solicitud is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        persona = solicitud.persona
        return Response({'id': solicitud.id, 'identificador': persona.identificador_biometrico_externo, 'nombre': persona.nombre})


class LectorEnrolamientoProgresoView(APIView):
    """POST del agente: qué pide en este momento (muestra n de N, "Apoya el dedo"), para la pantalla."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, pk, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        solicitud = get_object_or_404(SolicitudEnrolamiento, pk=pk, punto_acceso=punto)
        serializer = ProgresoEnrolamientoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if solicitud.estado not in ENROL_ABIERTAS:
            return Response({'detail': f'La solicitud ya está {solicitud.estado}.'}, status=status.HTTP_409_CONFLICT)
        for campo, valor in serializer.validated_data.items():
            setattr(solicitud, campo, valor)
        solicitud.save(update_fields=['muestra', 'total_muestras', 'indicacion'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerificacionDetailView(APIView):
    """GET: estado de una verificación de identidad (la pantalla de la intervención lo consulta)."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, pk, format=None):
        solicitud = get_object_or_404(SolicitudVerificacion.objects.select_related('punto_acceso'), pk=pk)
        return Response(SolicitudVerificacionSerializer(solicitud).data)


class LectorVerificacionSiguienteView(APIView):
    """GET del agente: la próxima huella que debe verificar contra UNA persona (204 si no hay)."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        solicitud = servicio.tomar_verificacion(punto)
        if solicitud is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        persona = solicitud.persona
        return Response({'id': solicitud.id, 'identificador': persona.identificador_biometrico_externo, 'nombre': persona.nombre})


class LectorVerificacionProgresoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, pk, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        solicitud = get_object_or_404(SolicitudVerificacion, pk=pk, punto_acceso=punto)
        serializer = ProgresoVerificacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if solicitud.estado not in ENROL_ABIERTAS:
            return Response({'detail': f'La solicitud ya está {solicitud.estado}.'}, status=status.HTTP_409_CONFLICT)
        for campo, valor in serializer.validated_data.items():
            setattr(solicitud, campo, valor)
        solicitud.save(update_fields=['intento', 'total_intentos', 'indicacion'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class LectorVerificacionResultadoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, pk, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        solicitud = get_object_or_404(
            SolicitudVerificacion.objects.select_related('persona', 'punto_acceso', 'solicitada_por'), pk=pk, punto_acceso=punto,
        )
        serializer = ResultadoVerificacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if solicitud.estado not in ENROL_ABIERTAS:
            return Response({'detail': f'La solicitud ya está {solicitud.estado}.'}, status=status.HTTP_409_CONFLICT)
        d = serializer.validated_data
        servicio.informar_verificacion(solicitud, d['coincide'], (d['identificado'] or '').strip(), d['mensaje'])
        return Response(SolicitudVerificacionSerializer(solicitud).data)


class LectorBajaSiguienteView(APIView):
    """GET del agente: la próxima huella que debe borrar de su PC (204 si no hay ninguna)."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        baja = servicio.tomar_baja(punto)
        if baja is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'id': baja.id, 'identificador': baja.identificador, 'nombre': baja.nombre})


class LectorBajaResultadoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, pk, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        baja = get_object_or_404(BajaHuella, pk=pk, punto_acceso=punto)
        serializer = ResultadoEnrolamientoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if baja.estado != BAJA_PENDIENTE:
            return Response({'detail': f'La orden ya está {baja.estado}.'}, status=status.HTTP_409_CONFLICT)
        servicio.informar_baja(baja, serializer.validated_data['exito'], serializer.validated_data['mensaje'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class LectorEnrolamientoResultadoView(APIView):
    """POST del agente: resultado del enrolamiento. La huella nunca viaja: queda en el PC del lector."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, pk, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()
        solicitud = get_object_or_404(
            SolicitudEnrolamiento.objects.select_related('persona', 'punto_acceso', 'solicitada_por'), pk=pk, punto_acceso=punto,
        )
        serializer = ResultadoEnrolamientoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if solicitud.estado not in ENROL_ABIERTAS:
            return Response({'detail': f'La solicitud ya está {solicitud.estado}.'}, status=status.HTTP_409_CONFLICT)
        servicio.informar_enrolamiento(solicitud, serializer.validated_data['exito'], serializer.validated_data['mensaje'])
        return Response(SolicitudEnrolamientoSerializer(solicitud).data)


class IntentoLectorView(APIView):
    """POST del agente del lector (RF-ACC-01). Se autentica con X-Punto-Acceso + X-Device-Key.

    Responde la decisión para que el agente la muestre (y, a futuro, abra o no la puerta).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        punto = autenticar_lector(request)
        if punto is None:
            return _lector_no_valido()

        serializer = IntentoLectorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        evento, creado = servicio.registrar_intento(
            punto, str(d['evento_id']), d['estado'], d['identificador'].strip(), d['fecha_hora'], d['motivo'],
        )
        return Response(
            {
                'id': evento.id,
                'resultado': evento.resultado,
                'motivo': evento.motivo,
                'persona': evento.persona.nombre if evento.persona else None,
                'duplicado': not creado,
            },
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK,
        )
