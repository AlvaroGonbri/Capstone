import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { RolUsuario } from '../models';
import { AuthService } from '../services/auth.service';

/** Permite la ruta solo a los roles indicados; el API vuelve a verificarlo. */
export function rolGuard(...roles: RolUsuario[]): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    return auth.tieneRol(...roles) ? true : inject(Router).createUrlTree(['/panel']);
  };
}
