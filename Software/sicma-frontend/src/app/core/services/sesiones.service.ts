import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SesionActiva } from '../models';

/** Sesiones activas: solo Administrador y Administrador Privilegiado (el API lo vuelve a verificar). */
@Injectable({ providedIn: 'root' })
export class SesionesService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/auth/sesiones/`;

  listar(): Observable<SesionActiva[]> {
    return this.http.get<SesionActiva[]>(this.url);
  }

  /** Cierra una sesión al instante. */
  revocar(sesion: string): Observable<{ revocadas: number }> {
    return this.http.post<{ revocadas: number }>(`${this.url}revocar/`, { sesion });
  }

  /** Cierra todas las sesiones de un usuario (menos la propia actual). */
  revocarUsuario(usuario: number): Observable<{ revocadas: number }> {
    return this.http.post<{ revocadas: number }>(`${this.url}revocar/`, { usuario });
  }
}
