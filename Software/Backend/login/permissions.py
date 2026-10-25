from rest_framework.permissions import BasePermission
from rest_framework.exceptions import AuthenticationFailed

from .serializers import get_user_role


# Roles que pueden consultar los módulos de monitoreo (matriz de permisos, columna C).
READ_ROLES = ('administrador', 'administradorprivilegiado', 'jefatura', 'tecnico', 'auditor')
# Roles que mantienen catálogos y configuración (matriz de permisos, columna C/E).
ADMIN_ROLES = ('administrador', 'administradorprivilegiado')
# Activos: el Técnico también registra y edita (HU-04, matriz "Activos y ubicaciones").
ACTIVO_EDIT_ROLES = ADMIN_ROLES + ('tecnico',)
# Personal externo: lo enrola y habilita el Departamento de contratistas (y el Administrador).
CONTRATISTAS_ROLES = ADMIN_ROLES + ('contratistas',)
# Reconocer y cerrar alertas: quien atiende el problema en terreno.
ALERTA_GESTION_ROLES = ADMIN_ROLES + ('tecnico',)
# Registro de accesos (RF-ACC-03): información sensible; no la ve el Técnico.
REGISTRO_ACCESOS_ROLES = ADMIN_ROLES + ('jefatura', 'auditor')
# Cancelar una intervención: la administra el Administrador y la aprueba la Jefatura.
CANCELAR_INTERVENCION_ROLES = ADMIN_ROLES + ('jefatura',)
# Solo el Administrador Privilegiado gestiona cuentas de administración y la política de seguridad.
PRIVILEGIADO = 'administradorprivilegiado'
GRUPOS_ADMINISTRACION = ('Administrador', 'AdministradorPrivilegiado')


def es_privilegiado(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name='AdministradorPrivilegiado').exists()


class RolePermission(BasePermission):
    message = 'Su perfil no tiene permiso para realizar esta operación.'

    def has_permission(self, request, view):
        try:
            role = get_user_role(request.user)
        except AuthenticationFailed:
            return False
        return role in getattr(view, 'allowed_roles', ())


class AdministratorPermission(BasePermission):
    message = 'Solo Administrador o AdministradorPrivilegiado puede realizar esta operación.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.groups.filter(
            name__in=('Administrador', 'AdministradorPrivilegiado'),
        ).exists()
