import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

/** Agrega el token de sesion a cada llamada al API. */
export const tokenInterceptor: HttpInterceptorFn = (peticion, siguiente) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = auth.token();
  if (!token) {
    return siguiente(peticion);
  }

  const peticionAutenticada = peticion.clone({
    setHeaders: { Authorization: `Bearer ${token}` },
  });

  return siguiente(peticionAutenticada).pipe(
    catchError((error: { status?: number; error?: { code?: string } }) => {
      const esEndpointDeAutenticacion =
        peticion.url.includes('/auth/token/') || peticion.url.includes('/auth/logout/');
      if (error.status !== 401 || esEndpointDeAutenticacion) {
        return throwError(() => error);
      }
      // Un administrador cerró esta sesión: no se intenta renovar, se sale y se avisa en el ingreso.
      if (error.error?.code === 'sesion_revocada') {
        if (auth.token()) {
          auth.cerrarSesion(true);
          void router.navigate(['/login'], { queryParams: { sesionExpirada: 'revocada' } });
        }
        return throwError(() => error);
      }

      return auth.renovarAccessToken().pipe(
        switchMap((nuevoToken) =>
          siguiente(
            peticion.clone({
              setHeaders: { Authorization: `Bearer ${nuevoToken}` },
            }),
          ),
        ),
        catchError((errorRenovacion) => {
          auth.cerrarSesion();
          return throwError(() => errorRenovacion);
        }),
      );
    }),
  );
};
