import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, delay, of, tap, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SesionIniciada, Usuario } from '../models';
import { USUARIOS_DEMO } from '../mock/datos-simulados';

const CLAVE_ALMACENAMIENTO = 'sicma.sesion';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  private readonly sesion = signal<SesionIniciada | null>(leerSesionGuardada());

  readonly usuario = computed<Usuario | null>(() => this.sesion()?.usuario ?? null);
  readonly token = computed<string | null>(() => this.sesion()?.token ?? null);
  readonly autenticado = computed(() => this.sesion() !== null);

  iniciarSesion(correo: string, clave: string): Observable<SesionIniciada> {
    if (environment.usarDatosSimulados) {
      const encontrado = USUARIOS_DEMO.find(
        (u) => u.correo.toLowerCase() === correo.trim().toLowerCase() && u.clave === clave,
      );
      if (!encontrado) {
        return throwError(() => new Error('Correo o clave incorrectos.')).pipe(delay(350));
      }
      const { clave: _omitida, ...usuario } = encontrado;
      return of({ usuario, token: 'token-de-demostracion' }).pipe(
        delay(350),
        tap((s) => this.guardar(s)),
      );
    }

    return this.http
      .post<SesionIniciada>(`${environment.apiUrl}/auth/login/`, { correo, clave })
      .pipe(tap((s) => this.guardar(s)));
  }

  cerrarSesion(): void {
    this.sesion.set(null);
    try {
      localStorage.removeItem(CLAVE_ALMACENAMIENTO);
    } catch {
      /* almacenamiento no disponible */
    }
  }

  private guardar(sesion: SesionIniciada): void {
    this.sesion.set(sesion);
    try {
      localStorage.setItem(CLAVE_ALMACENAMIENTO, JSON.stringify(sesion));
    } catch {
      /* almacenamiento no disponible */
    }
  }
}

function leerSesionGuardada(): SesionIniciada | null {
  try {
    const bruto = localStorage.getItem(CLAVE_ALMACENAMIENTO);
    return bruto ? (JSON.parse(bruto) as SesionIniciada) : null;
  } catch {
    return null;
  }
}
