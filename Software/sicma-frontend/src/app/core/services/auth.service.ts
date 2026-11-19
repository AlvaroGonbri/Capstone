import { DOCUMENT } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, delay, from, map, of, switchMap, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { RolUsuario, SesionIniciada, Usuario } from '../models';
import { USUARIOS_DEMO } from '../mock/datos-simulados';
import { BiometriaService } from './biometria.service';

const CLAVE_ALMACENAMIENTO = 'sicma.sesion';
const CLAVE_ULTIMA_ACTIVIDAD = 'sicma.ultimaActividad';
const TIEMPO_INACTIVIDAD_POR_DEFECTO_MINUTOS = 15;
const EVENTOS_ACTIVIDAD = ['keydown', 'mousedown', 'pointerdown', 'scroll', 'touchstart'];

interface RespuestaToken {
  access: string;
  refresh: string;
  /** App móvil: llave para entrar después con huella o PIN (ver BiometriaService). */
  llave?: string;
}

interface RespuestaUsuario extends Omit<Usuario, 'inactivityTimeoutMinutes'> {
  inactivity_timeout_minutes: number;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly document = inject(DOCUMENT);
  private readonly router = inject(Router);
  private readonly biometria = inject(BiometriaService);

  private readonly sesion = signal<SesionIniciada | null>(leerSesionGuardada());
  private temporizadorInactividad: ReturnType<typeof setTimeout> | null = null;
  private ultimaActividadPersistida = 0;
  /** Llave recibida en el último ingreso con contraseña, hasta que la persona decida activar la huella. */
  private llavePendiente: string | null = null;

  readonly usuario = computed<Usuario | null>(() => this.sesion()?.usuario ?? null);
  readonly token = computed<string | null>(() => this.sesion()?.token ?? null);
  readonly autenticado = computed(() => this.sesion() !== null);

  /** App móvil (RF-PLT-02): solo consulta. El backend lo impone con tokens de solo lectura. */
  readonly soloConsulta = environment.soloConsulta;

  /** Solo para mostrar u ocultar acciones: el API vuelve a verificar el rol (RNF-SEG-08). */
  tieneRol(...roles: RolUsuario[]): boolean {
    const rol = this.usuario()?.rol;
    return rol !== undefined && roles.includes(rol);
  }

  /** Si el usuario puede hacer cambios: tiene el rol y no está en la app móvil de consulta. */
  puedeModificar(...roles: RolUsuario[]): boolean {
    return !this.soloConsulta && this.tieneRol(...roles);
  }

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
    this.llavePendiente = null;
    return this.http
      .post<RespuestaToken>(`${environment.apiUrl}/auth/token/`, {
        username: identificador.trim(),
        password: clave,
        canal: environment.soloConsulta ? 'movil' : 'web',
      })
      .pipe(
        tap((tokens) => (this.llavePendiente = tokens.llave ?? null)),
        switchMap((tokens) => this.abrirSesion(tokens)),
        catchError((error: { error?: { detail?: string; code?: string } }) =>
          throwError(() =>
            Object.assign(new Error(error.error?.detail ?? 'No fue posible iniciar sesión.'), {
              codigo: error.error?.code,
            }),
          ),
        ),
      );
  }

  /** La llave del último ingreso con contraseña (una sola vez), para ofrecer activar la huella. */
  tomarLlavePendiente(): string | null {
    const llave = this.llavePendiente;
    this.llavePendiente = null;
    return llave;
  }

  /**
   * App móvil: pide la huella o el PIN del teléfono y entra sin contraseña.
   * Si la persona cancela, el error lleva codigo 'huella_cancelada' (no hay que mostrar nada).
   */
  iniciarSesionConHuella(): Observable<SesionIniciada> {
    this.sesion.set(null);
    return from(
      this.biometria.desbloquear().catch(() => {
        throw Object.assign(new Error('No se verificó la huella.'), { codigo: 'huella_cancelada' });
      }),
    ).pipe(
      switchMap((llave) =>
        this.http.post<RespuestaToken>(`${environment.apiUrl}/auth/token/dispositivo/`, { llave }),
      ),
      // La llave es de un solo uso: se guarda la nueva que entregó el servidor.
      switchMap((tokens) =>
        from(this.biometria.guardar(tokens.llave ?? '', this.biometria.activa() ?? '')).pipe(map(() => tokens)),
      ),
      switchMap((tokens) => this.abrirSesion(tokens)),
      catchError((error: (HttpErrorResponse | Error) & { codigo?: string }) => {
        if (error instanceof HttpErrorResponse) {
          if (error.status === 401) {
            void this.biometria.olvidar(); // venció, se cambió la contraseña o se cerró sesión en otro lado
          }
          const detalle = (error.error as { detail?: string; code?: string } | null) ?? {};
          return throwError(() =>
            Object.assign(new Error(detalle.detail ?? 'No fue posible entrar con la huella.'), {
              codigo: detalle.code,
            }),
          );
        }
        return throwError(() => error);
      }),
    );
  }

  /**
   * Cierra la sesión. `olvidarDispositivo` (botón "Salir" en la app móvil) también apaga el ingreso
   * con huella en el teléfono; el cierre por inactividad no, para poder desbloquear con la huella.
   */
  cerrarSesion(olvidarDispositivo = false): void {
    const refreshToken = this.sesion()?.refreshToken;
    const accessToken = this.sesion()?.token;
    const avisarAlServidor = (llave: string | null) => {
      if (!refreshToken) {
        return;
      }
      // El token se pasa a mano: cuando esto corre, la sesión local ya se borró.
      this.http
        .post(`${environment.apiUrl}/auth/logout/`, llave ? { refresh: refreshToken, llave } : { refresh: refreshToken }, {
          headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        })
        .subscribe({ error: () => undefined });
    };
    if (olvidarDispositivo && this.biometria.activa()) {
      void this.biometria.llaveParaInvalidar().then((llave) => {
        avisarAlServidor(llave);
        void this.biometria.olvidar();
      });
    } else {
      avisarAlServidor(null);
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

  /** Con los tokens recién emitidos, trae los datos del usuario y deja la sesión iniciada. */
  private abrirSesion(tokens: RespuestaToken): Observable<SesionIniciada> {
    return this.http
      .get<RespuestaUsuario>(`${environment.apiUrl}/auth/me/`, {
        headers: { Authorization: `Bearer ${tokens.access}` },
      })
      .pipe(
        map(({ inactivity_timeout_minutes, ...usuario }) => ({
          usuario: { ...usuario, inactivityTimeoutMinutes: inactivity_timeout_minutes },
          token: tokens.access,
          refreshToken: tokens.refresh,
        })),
        tap((s) => this.guardar(s)),
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
