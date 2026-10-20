import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  // La gestión de usuarios no está disponible en la app móvil (solo consulta).
  return auth.puedeModificar('administrador', 'administradorprivilegiado')
    ? true
    : router.createUrlTree(['/panel']);
};
