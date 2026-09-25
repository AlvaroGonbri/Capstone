import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';

/** Agrega el token de sesion a cada llamada al API. */
export const tokenInterceptor: HttpInterceptorFn = (peticion, siguiente) => {
  const token = inject(AuthService).token();
  if (!token) {
    return siguiente(peticion);
  }
  return siguiente(
    peticion.clone({ setHeaders: { Authorization: `Bearer ${token}` } }),
  );
};
