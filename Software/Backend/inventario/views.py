from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from login.permissions import ACTIVO_EDIT_ROLES, ADMIN_ROLES, READ_ROLES, RolePermission

from .models import ESTADO_RETIRADO, Activo, EstadoActivo, TipoActivo
from .serializers import (
    ActivoFilterSerializer,
    ActivoReadSerializer,
    ActivoWriteSerializer,
    EstadoActivoSerializer,
    HistorialActivoSerializer,
    TipoActivoSerializer,
    nombre_usuario,
)


class ActivoPermisosMixin:
    """Consultan todos los roles; registran y editan Administrador y Técnico."""

    permission_classes = [RolePermission]

    @property
    def allowed_roles(self):
        return READ_ROLES if self.request.method == 'GET' else ACTIVO_EDIT_ROLES


def _activos():
    return Activo.objects.select_related('ubicacion', 'responsable')


class ActivoListView(ActivoPermisosMixin, APIView):
    """GET: inventario con búsqueda y filtros (RF-ACT-02). POST: alta (RF-ACT-01)."""

    def get(self, request, format=None):
        filtros = ActivoFilterSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        datos = filtros.validated_data
        activos = _activos()
        if datos.get('q'):
            texto = datos['q'].strip()
            activos = activos.filter(
                Q(codigo__icontains=texto) | Q(nombre__icontains=texto) | Q(numero_serie__icontains=texto)
                | Q(marca__icontains=texto) | Q(modelo__icontains=texto)
            )
        if datos.get('tipo'):
            activos = activos.filter(tipo=datos['tipo'])
        if datos.get('ubicacion'):
            activos = activos.filter(ubicacion_id=datos['ubicacion'])
        if datos.get('estado'):
            activos = activos.filter(estado=datos['estado'])
        elif not datos['incluir_retirados']:
            activos = activos.exclude(estado=ESTADO_RETIRADO)
        return Response(ActivoReadSerializer(activos.order_by('codigo'), many=True).data)

    def post(self, request, format=None):
        serializer = ActivoWriteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        activo = serializer.save()
        return Response(ActivoReadSerializer(_activos().get(pk=activo.pk)).data, status=status.HTTP_201_CREATED)


class ActivoDetailView(ActivoPermisosMixin, APIView):
    """GET y PATCH de un activo. No hay DELETE: se da de baja con estado 'Retirado' (RN-02)."""

    def get(self, request, pk, format=None):
        return Response(ActivoReadSerializer(get_object_or_404(_activos(), pk=pk)).data)

    def patch(self, request, pk, format=None):
        activo = get_object_or_404(_activos(), pk=pk)
        serializer = ActivoWriteSerializer(activo, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ActivoReadSerializer(_activos().get(pk=pk)).data)


class ActivoHistorialView(APIView):
    """GET: historial de cambios de un activo, del más reciente al más antiguo (RF-ACT-03)."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, pk, format=None):
        activo = get_object_or_404(Activo, pk=pk)
        historial = activo.historial.select_related('usuario').order_by('-fecha_hora', '-id')
        return Response(HistorialActivoSerializer(historial, many=True).data)


class ResponsablesPosiblesView(APIView):
    """GET: usuarios activos que pueden quedar como responsables de un activo."""
    permission_classes = [RolePermission]
    allowed_roles = READ_ROLES

    def get(self, request, format=None):
        usuarios = get_user_model().objects.filter(is_active=True).order_by('first_name', 'username')
        return Response([
            {'id': u.id, 'nombre': nombre_usuario(u), 'email': u.email or None} for u in usuarios
        ])


class CatalogoPermisosMixin:
    """Consultan todos los roles; mantiene el catálogo el Administrador."""

    permission_classes = [RolePermission]

    @property
    def allowed_roles(self):
        return READ_ROLES if self.request.method == 'GET' else ADMIN_ROLES


class TipoActivoListView(CatalogoPermisosMixin, APIView):
    """GET: catálogo de tipos (?todos=1 incluye desactivados). POST: alta (RF-CAT-03)."""

    def get(self, request, format=None):
        tipos = TipoActivo.objects.all()
        if request.query_params.get('todos') != '1':
            tipos = tipos.filter(activo=True)
        return Response(TipoActivoSerializer(tipos, many=True).data)

    def post(self, request, format=None):
        serializer = TipoActivoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(TipoActivoSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


class TipoActivoDetailView(CatalogoPermisosMixin, APIView):
    """PATCH: renombra o desactiva un tipo. Al renombrar, los activos de ese tipo se actualizan."""

    def patch(self, request, pk, format=None):
        tipo = get_object_or_404(TipoActivo, pk=pk)
        nombre_anterior = tipo.nombre
        serializer = TipoActivoSerializer(tipo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            tipo = serializer.save()
            if tipo.nombre != nombre_anterior:
                Activo.objects.filter(tipo=nombre_anterior).update(tipo=tipo.nombre)
        return Response(TipoActivoSerializer(tipo).data)


class EstadoActivoListView(CatalogoPermisosMixin, APIView):
    """GET: catálogo de estados (?todos=1 incluye desactivados). POST: alta (RF-CAT-03)."""

    def get(self, request, format=None):
        estados = EstadoActivo.objects.all()
        if request.query_params.get('todos') != '1':
            estados = estados.filter(activo=True)
        return Response(EstadoActivoSerializer(estados, many=True).data)

    def post(self, request, format=None):
        serializer = EstadoActivoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(EstadoActivoSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


class EstadoActivoDetailView(CatalogoPermisosMixin, APIView):
    """PATCH: cambia etiqueta, color, orden o vigencia. Los estados de sistema no se desactivan."""

    def patch(self, request, pk, format=None):
        estado = get_object_or_404(EstadoActivo, pk=pk)
        serializer = EstadoActivoSerializer(estado, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(EstadoActivoSerializer(serializer.save()).data)
