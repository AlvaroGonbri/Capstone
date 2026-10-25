import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { RolUsuario } from '../models';
import { AuthService } from '../services/auth.service';

/** Rutas de edición: solo los roles indicados y nunca en la app móvil de consulta. El API vuelve a verificarlo. */
export function rolGuard(...roles: RolUsuario[]): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    return auth.puedeModificar(...roles) ? true : inject(Router).createUrlTree(['/panel']);
  };
}

/** Rutas de consulta que algunos roles no deben ver (p. ej. el registro de accesos para el Técnico). */
export function excluirRolesGuard(...roles: RolUsuario[]): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    return auth.tieneRol(...roles) ? inject(Router).createUrlTree(['/panel']) : true;
  };
}
