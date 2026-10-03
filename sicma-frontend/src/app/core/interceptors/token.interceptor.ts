import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

/** Agrega el token de sesion a cada llamada al API. */
export const tokenInterceptor: HttpInterceptorFn = (peticion, siguiente) => {
  const auth = inject(AuthService);
  const token = auth.token();
  if (!token) {
    return siguiente(peticion);
  }

  const peticionAutenticada = peticion.clone({
    setHeaders: { Authorization: `Bearer ${token}` },
  });

  return siguiente(peticionAutenticada).pipe(
    catchError((error: { status?: number }) => {
      const esEndpointDeAutenticacion =
        peticion.url.includes('/auth/token/') || peticion.url.includes('/auth/logout/');
      if (error.status !== 401 || esEndpointDeAutenticacion) {
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
