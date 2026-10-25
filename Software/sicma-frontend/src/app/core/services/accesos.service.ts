import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  CambioHabilitacion,
  EventoAcceso,
  PermisoAcceso,
  PersonaAutorizada,
  PuntoAcceso,
  ResultadoAcceso,
  SolicitudEnrolamiento,
  VentanaPermiso,
} from '../models';

export interface FiltrosEventos {
  desde?: string;
  hasta?: string;
  resultado?: ResultadoAcceso;
  punto?: number;
  persona?: number;
  q?: string;
}

export interface DatosPermiso {
  persona: number;
  punto_acceso: number;
  vigencia_inicio: string;
  vigencia_fin: string | null;
  dias: VentanaPermiso[];
}

/** Control de acceso físico (RF-ACC). Los eventos los crea solo el agente del lector. */
@Injectable({ providedIn: 'root' })
export class AccesosService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/accesos/`;

  eventos(filtros: FiltrosEventos = {}): Observable<EventoAcceso[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    const params: Record<string, string> = {};
    for (const [clave, valor] of Object.entries(filtros)) {
      if (valor !== undefined && valor !== null && valor !== '') {
        params[clave] = String(valor);
      }
    }
    return this.http.get<EventoAcceso[]>(`${this.url}eventos/`, { params });
  }

  /** `q` busca por nombre, RUT, empresa o identificador. */
  personas(q = ''): Observable<PersonaAutorizada[]> {
    return this.http.get<PersonaAutorizada[]>(`${this.url}personas/`, { params: q ? { q } : {} });
  }

  persona(id: number): Observable<PersonaAutorizada> {
    return this.http.get<PersonaAutorizada>(`${this.url}personas/${id}/`);
  }

  crearPersona(datos: Pick<PersonaAutorizada, 'nombre' | 'rut' | 'empresa'>): Observable<PersonaAutorizada> {
    return this.http.post<PersonaAutorizada>(`${this.url}personas/`, datos);
  }

  editarPersona(id: number, datos: Partial<Pick<PersonaAutorizada, 'nombre' | 'rut' | 'empresa'>>): Observable<PersonaAutorizada> {
    return this.http.patch<PersonaAutorizada>(`${this.url}personas/${id}/`, datos);
  }

  /** Borra la ficha; los lectores borran su huella y el registro de accesos se conserva. */
  eliminarPersona(id: number): Observable<{ lectores_notificados: number }> {
    return this.http.delete<{ lectores_notificados: number }>(`${this.url}personas/${id}/`);
  }

  /** Alta o baja manual para trabajar en el datacenter; deshabilitar exige motivo. */
  cambiarHabilitacion(id: number, habilitada: boolean, motivo: string): Observable<PersonaAutorizada> {
    return this.http.post<PersonaAutorizada>(`${this.url}personas/${id}/habilitacion/`, { habilitada, motivo });
  }

  historialHabilitacion(id: number): Observable<CambioHabilitacion[]> {
    return this.http.get<CambioHabilitacion[]>(`${this.url}personas/${id}/habilitacion/`);
  }

  /** Pide al agente del lector que capture la huella; la persona debe estar frente al lector. */
  enrolar(id: number, puntoAcceso?: number): Observable<SolicitudEnrolamiento> {
    return this.http.post<SolicitudEnrolamiento>(`${this.url}personas/${id}/enrolar/`, puntoAcceso ? { punto_acceso: puntoAcceso } : {});
  }

  enrolamiento(id: number): Observable<SolicitudEnrolamiento> {
    return this.http.get<SolicitudEnrolamiento>(`${this.url}enrolamientos/${id}/`);
  }

  cancelarEnrolamiento(id: number): Observable<SolicitudEnrolamiento> {
    return this.http.post<SolicitudEnrolamiento>(`${this.url}enrolamientos/${id}/cancelar/`, {});
  }

  puntos(): Observable<PuntoAcceso[]> {
    return this.http.get<PuntoAcceso[]>(`${this.url}puntos/`);
  }

  crearPunto(datos: Pick<PuntoAcceso, 'nombre' | 'ubicacion'>): Observable<PuntoAcceso & { clave_dispositivo: string }> {
    return this.http.post<PuntoAcceso & { clave_dispositivo: string }>(`${this.url}puntos/`, datos);
  }

  editarPunto(id: number, datos: Partial<PuntoAcceso>): Observable<PuntoAcceso> {
    return this.http.patch<PuntoAcceso>(`${this.url}puntos/${id}/`, datos);
  }

  regenerarClave(id: number): Observable<{ id: number; nombre: string; clave_dispositivo: string }> {
    return this.http.post<{ id: number; nombre: string; clave_dispositivo: string }>(`${this.url}puntos/${id}/clave/`, {});
  }

  permisos(): Observable<PermisoAcceso[]> {
    return this.http.get<PermisoAcceso[]>(`${this.url}permisos/`);
  }

  crearPermiso(datos: DatosPermiso): Observable<PermisoAcceso> {
    return this.http.post<PermisoAcceso>(`${this.url}permisos/`, datos);
  }

  editarPermiso(id: number, datos: Partial<DatosPermiso & { estado: 'Activo' | 'Revocado' }>): Observable<PermisoAcceso> {
    return this.http.patch<PermisoAcceso>(`${this.url}permisos/${id}/`, datos);
  }
}
