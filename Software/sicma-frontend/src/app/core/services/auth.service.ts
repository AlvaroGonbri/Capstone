import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, delay, map, of, switchMap, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SesionIniciada, Usuario } from '../models';
import { USUARIOS_DEMO } from '../mock/datos-simulados';

const CLAVE_ALMACENAMIENTO = 'sicma.sesion';
const CLAVE_ULTIMA_ACTIVIDAD = 'sicma.ultimaActividad';
const TIEMPO_INACTIVIDAD_POR_DEFECTO_MINUTOS = 15;
const EVENTOS_ACTIVIDAD = ['keydown', 'mousedown', 'pointerdown', 'scroll', 'touchstart'];

interface RespuestaToken {
  access: string;
  refresh: string;
}

interface RespuestaUsuario extends Omit<Usuario, 'inactivityTimeoutMinutes'> {
  inactivity_timeout_minutes: number;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly document = inject(DOCUMENT);
  private readonly router = inject(Router);

  private readonly sesion = signal<SesionIniciada | null>(leerSesionGuardada());
  private temporizadorInactividad: ReturnType<typeof setTimeout> | null = null;
  private ultimaActividadPersistida = 0;

  readonly usuario = computed<Usuario | null>(() => this.sesion()?.usuario ?? null);
  readonly token = computed<string | null>(() => this.sesion()?.token ?? null);
  readonly autenticado = computed(() => this.sesion() !== null);

  iniciarControlInactividad(): void {
    for (const evento of EVENTOS_ACTIVIDAD) {
      this.document.addEventListener(evento, this.registrarActividad, { passive: true });
    }

    if (this.sesion()) {
      this.programarCierre();
    }
  }

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
            .get<RespuestaUsuario>(`${environment.apiUrl}/auth/me/`, {
              headers: { Authorization: `Bearer ${tokens.access}` },
            })
            .pipe(
              map(({ inactivity_timeout_minutes, ...usuario }) => ({
                usuario: { ...usuario, inactivityTimeoutMinutes: inactivity_timeout_minutes },
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
    this.detenerTemporizador();
    try {
      sessionStorage.removeItem(CLAVE_ALMACENAMIENTO);
      sessionStorage.removeItem(CLAVE_ULTIMA_ACTIVIDAD);
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
    this.registrarActividad();
    try {
      sessionStorage.setItem(CLAVE_ALMACENAMIENTO, JSON.stringify(sesion));
      localStorage.removeItem(CLAVE_ALMACENAMIENTO);
    } catch {
      /* almacenamiento no disponible */
    }
  }

  private readonly registrarActividad = (): void => {
    if (!this.sesion()) {
      return;
    }

    const ahora = Date.now();
    if (ahora - this.ultimaActividadPersistida >= 30_000) {
      this.ultimaActividadPersistida = ahora;
      this.enviarActividadAlBackend();
      try {
        sessionStorage.setItem(CLAVE_ULTIMA_ACTIVIDAD, String(ahora));
      } catch {
        /* almacenamiento no disponible */
      }
    }
    this.programarCierre();
  };

  private enviarActividadAlBackend(): void {
    if (!this.sesion()) {
      return;
    }
    this.http.post(`${environment.apiUrl}/auth/activity/`, {}).subscribe({
      error: () => undefined,
    });
  }

  private programarCierre(): void {
    this.detenerTemporizador();
    let ultimaActividad = Date.now();
    try {
      const guardada = Number(sessionStorage.getItem(CLAVE_ULTIMA_ACTIVIDAD));
      if (Number.isFinite(guardada) && guardada > 0) {
        ultimaActividad = guardada;
      }
    } catch {
      /* almacenamiento no disponible */
    }

    const timeoutMinutes =
      this.sesion()?.usuario.inactivityTimeoutMinutes ??
      TIEMPO_INACTIVIDAD_POR_DEFECTO_MINUTOS;
    const timeoutMs = timeoutMinutes * 60 * 1000;
    const restante = Math.max(timeoutMs - (Date.now() - ultimaActividad), 0);
    this.temporizadorInactividad = setTimeout(() => {
      if (!this.sesion()) {
        return;
      }
      this.cerrarSesion();
      void this.router.navigate(['/login'], {
        queryParams: { sesionExpirada: 'inactividad' },
      });
    }, restante);
  }

  private detenerTemporizador(): void {
    if (this.temporizadorInactividad !== null) {
      clearTimeout(this.temporizadorInactividad);
      this.temporizadorInactividad = null;
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
