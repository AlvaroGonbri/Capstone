import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, delay, map, of, switchMap, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SesionIniciada, Usuario } from '../models';
import { USUARIOS_DEMO } from '../mock/datos-simulados';

const CLAVE_ALMACENAMIENTO = 'sicma.sesion';

interface RespuestaToken {
  access: string;
  refresh: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  private readonly sesion = signal<SesionIniciada | null>(leerSesionGuardada());

  readonly usuario = computed<Usuario | null>(() => this.sesion()?.usuario ?? null);
  readonly token = computed<string | null>(() => this.sesion()?.token ?? null);
  readonly autenticado = computed(() => this.sesion() !== null);

  iniciarSesion(identificador: string, clave: string): Observable<SesionIniciada> {
    if (environment.usarDatosSimulados) {
      const encontrado = USUARIOS_DEMO.find(
        (u) =>
          (u.correo.toLowerCase() === identificador.trim().toLowerCase() ||
            u.correo.split('@')[0].toLowerCase() === identificador.trim().toLowerCase()) &&
          u.clave === clave,
      );
      if (!encontrado) {
        return throwError(() => new Error('Correo o clave incorrectos.')).pipe(delay(350));
      }
      const { clave: _omitida, ...usuario } = encontrado;
      return of({
        usuario,
        token: 'token-de-demostracion',
        refreshToken: 'refresh-de-demostracion',
      }).pipe(
        delay(350),
        tap((s) => this.guardar(s)),
      );
    }

    this.sesion.set(null);
    return this.http
      .post<RespuestaToken>(`${environment.apiUrl}/auth/token/`, {
        username: identificador.trim(),
        password: clave,
      })
      .pipe(
        switchMap((tokens) =>
          this.http
            .get<Usuario>(`${environment.apiUrl}/auth/me/`, {
              headers: { Authorization: `Bearer ${tokens.access}` },
            })
            .pipe(
              map((usuario) => ({
                usuario,
                token: tokens.access,
                refreshToken: tokens.refresh,
              })),
            ),
        ),
        tap((s) => this.guardar(s)),
        catchError((error: { error?: { detail?: string } }) =>
          throwError(
            () => new Error(error.error?.detail ?? 'No fue posible iniciar sesión.'),
          ),
        ),
      );
  }

  cerrarSesion(): void {
    const refreshToken = this.sesion()?.refreshToken;
    if (refreshToken) {
      this.http.post(`${environment.apiUrl}/auth/logout/`, { refresh: refreshToken }).subscribe({
        error: () => undefined,
      });
    }

    this.sesion.set(null);
    try {
      sessionStorage.removeItem(CLAVE_ALMACENAMIENTO);
      localStorage.removeItem(CLAVE_ALMACENAMIENTO);
    } catch {
      /* almacenamiento no disponible */
    }
  }

  renovarAccessToken(): Observable<string> {
    const refreshToken = this.sesion()?.refreshToken;
    if (!refreshToken) {
      return throwError(() => new Error('La sesión ha expirado.'));
    }

    return this.http
      .post<Pick<RespuestaToken, 'access'>>(`${environment.apiUrl}/auth/token/refresh/`, {
        refresh: refreshToken,
      })
      .pipe(
        map(({ access }) => {
          const sesion = this.sesion();
          if (!sesion) {
            throw new Error('La sesión ha expirado.');
          }
          this.guardar({ ...sesion, token: access });
          return access;
        }),
      );
  }

  private guardar(sesion: SesionIniciada): void {
    this.sesion.set(sesion);
    try {
      sessionStorage.setItem(CLAVE_ALMACENAMIENTO, JSON.stringify(sesion));
      localStorage.removeItem(CLAVE_ALMACENAMIENTO);
    } catch {
      /* almacenamiento no disponible */
    }
  }
}

function leerSesionGuardada(): SesionIniciada | null {
  try {
    const bruto = sessionStorage.getItem(CLAVE_ALMACENAMIENTO);
    return bruto ? (JSON.parse(bruto) as SesionIniciada) : null;
  } catch {
    return null;
  }
}
