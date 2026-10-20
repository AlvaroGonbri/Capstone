from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from login.permissions import ADMIN_ROLES, READ_ROLES, RolePermission

from . import servicio
from .models import ESTADOS_INTERVENCION, Intervencion, IntervencionActivo
from .serializers import (
    ROLES_ASIGNABLES,
    AsignacionSerializer,
    CancelacionSerializer,
    CierreSerializer,
    IntervencionSerializer,
    nombre_usuario,
    rol_de,
)


def _intervenciones():
    return Intervencion.objects.select_related('responsable').prefetch_related(
        Prefetch('activos_afectados', queryset=IntervencionActivo.objects.select_related('activo')),
        'decisiones__decisor',
    )


class IntervencionListView(APIView):
    """GET: intervenciones, de la más reciente a la más antigua. Filtros ?estado= y ?activo=."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        intervenciones = _intervenciones().order_by('-id')
        estado = request.query_params.get('estado')
        if estado:
            if estado not in ESTADOS_INTERVENCION:
                return Response({'estado': 'Estado desconocido.'}, status=status.HTTP_400_BAD_REQUEST)
            intervenciones = intervenciones.filter(estado=estado)
        activo = request.query_params.get('activo')
        if activo:
            if not activo.isdigit():
                return Response({'activo': 'Debe ser un id.'}, status=status.HTTP_400_BAD_REQUEST)
            intervenciones = intervenciones.filter(activos_afectados__activo_id=int(activo))
        return Response(IntervencionSerializer(intervenciones, many=True).data)


class IntervencionDetailView(APIView):
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, pk, format=None):
        return Response(IntervencionSerializer(get_object_or_404(_intervenciones(), pk=pk)).data)


class TecnicosView(APIView):
    """GET: usuarios a los que se puede asignar una intervención."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        usuarios = get_user_model().objects.filter(is_active=True).prefetch_related('groups').order_by('first_name', 'username')
        return Response([
            {'id': u.id, 'nombre': nombre_usuario(u), 'email': u.email or None, 'rol': rol_de(u)}
            for u in usuarios if rol_de(u) in ROLES_ASIGNABLES
        ])


class AccionIntervencionView(APIView):
    """Base de las acciones (POST): un estado que no permite la operación responde 409."""
    permission_classes = [RolePermission]
    serializer_class = None

    def post(self, request, pk, format=None):
        intervencion = get_object_or_404(Intervencion.objects.select_related('responsable'), pk=pk)
        datos = None
        if self.serializer_class:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            datos = serializer.validated_data
        try:
            self.ejecutar(request, intervencion, datos)
        except servicio.TransicionInvalida as error:
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(IntervencionSerializer(_intervenciones().get(pk=pk)).data)

    def ejecutar(self, request, intervencion, datos):
        raise NotImplementedError


class SoloTecnicoAsignadoMixin:
    """Inicia y cierra el técnico asignado; un Administrador puede hacerlo en su lugar."""
    allowed_roles = ROLES_ASIGNABLES

    def verificar_tecnico(self, request, intervencion):
        if rol_de(request.user) == 'tecnico' and intervencion.responsable_id != request.user.id:
            raise PermissionDenied('Solo el técnico asignado puede registrar la ejecución.')


class AsignarView(AccionIntervencionView):
    """POST: asigna técnico, horario y activos (RF-INT-05). Solo Administrador."""
    allowed_roles = ADMIN_ROLES
    serializer_class = AsignacionSerializer

    def ejecutar(self, request, intervencion, datos):
        servicio.asignar(intervencion, datos['tecnico'], datos['fecha_inicio'], datos['fecha_termino'], datos.get('activos'))


class IniciarView(SoloTecnicoAsignadoMixin, AccionIntervencionView):
    """POST: el técnico registra el inicio (RF-INT-06)."""

    def ejecutar(self, request, intervencion, datos):
        self.verificar_tecnico(request, intervencion)
        servicio.iniciar(intervencion)


class CerrarView(SoloTecnicoAsignadoMixin, AccionIntervencionView):
    """POST: el técnico registra el cierre, exitoso o fallido, con su observación (RF-INT-06)."""
    serializer_class = CierreSerializer

    def ejecutar(self, request, intervencion, datos):
        self.verificar_tecnico(request, intervencion)
        servicio.cerrar(intervencion, datos['exitosa'], datos['observacion'].strip())


class CancelarView(AccionIntervencionView):
    """POST: el Administrador cancela una intervención pendiente o aprobada."""
    allowed_roles = ADMIN_ROLES
    serializer_class = CancelacionSerializer

    def ejecutar(self, request, intervencion, datos):
        servicio.cancelar(intervencion, datos['motivo'].strip())
