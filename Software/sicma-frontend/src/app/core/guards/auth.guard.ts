import { inject } from '@angular/core';
import { CanActivateFn, RedirectCommand, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/** Pantallas que ve el Departamento de contratistas: solo el personal externo. */
const RUTAS_CONTRATISTAS = ['/personal', '/cambiar-clave'];

/** Impide entrar a las pantallas internas sin sesion iniciada. */
export const authGuard: CanActivateFn = (_ruta, estado) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.autenticado()) {
    if (auth.tieneRol('contratistas') && !RUTAS_CONTRATISTAS.some((r) => estado.url.startsWith(r))) {
      return router.createUrlTree(['/personal']);
    }
    return true;
  }
  // El ingreso se muestra sin cambiar la dirección del navegador: queda la que escribió la persona
  // (p. ej. solo el dominio) y, tras iniciar sesión, se va a esa pantalla (volverA, que no se ve).
  const ingreso = router.createUrlTree(['/login'], { queryParams: { volverA: estado.url } });
  return new RedirectCommand(ingreso, { skipLocationChange: true });
};
