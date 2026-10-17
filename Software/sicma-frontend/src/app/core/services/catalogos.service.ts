import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SensorCatalogo, UbicacionCatalogo } from '../models';

export interface DatosUbicacion {
  sala: string;
  zona: string | null;
  rack: string | null;
  posicion: string | null;
  ubicacion_padre: number | null;
  activa: boolean;
}

export interface DatosSensor {
  codigo: string;
  tipo: string;
  ubicacion: number;
  estado: 'Activo' | 'Inactivo';
  intervalo_esperado_segundos: number;
}

/** Ubicaciones y zonas (RF-CAT-01, RF-CAT-04) y dispositivos IoT (RF-CAT-02). */
@Injectable({ providedIn: 'root' })
export class CatalogosService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  ubicaciones(incluirInactivas = false): Observable<UbicacionCatalogo[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    return this.http.get<UbicacionCatalogo[]>(`${this.api}/ubicaciones/`, {
      params: incluirInactivas ? { todas: '1' } : {},
    });
  }

  crearUbicacion(datos: DatosUbicacion): Observable<UbicacionCatalogo> {
    return this.http.post<UbicacionCatalogo>(`${this.api}/ubicaciones/`, datos);
  }

  actualizarUbicacion(id: number, datos: Partial<DatosUbicacion>): Observable<UbicacionCatalogo> {
    return this.http.patch<UbicacionCatalogo>(`${this.api}/ubicaciones/${id}/`, datos);
  }

  sensores(): Observable<SensorCatalogo[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    return this.http.get<SensorCatalogo[]>(`${this.api}/sensores/`);
  }

  /** La respuesta trae clave_dispositivo: se muestra una sola vez, SICMA guarda solo su hash. */
  crearSensor(datos: DatosSensor): Observable<SensorCatalogo & { clave_dispositivo: string }> {
    return this.http.post<SensorCatalogo & { clave_dispositivo: string }>(`${this.api}/sensores/`, datos);
  }

  actualizarSensor(id: number, datos: Partial<DatosSensor>): Observable<SensorCatalogo> {
    return this.http.patch<SensorCatalogo>(`${this.api}/sensores/${id}/`, datos);
  }

  regenerarClave(id: number): Observable<{ codigo: string; clave_dispositivo: string }> {
    return this.http.post<{ codigo: string; clave_dispositivo: string }>(`${this.api}/sensores/${id}/clave/`, {});
  }
}

export function nombreUbicacion(u: Pick<UbicacionCatalogo, 'sala' | 'zona' | 'rack' | 'posicion'>): string {
  return [u.sala, u.zona, u.rack, u.posicion].filter(Boolean).join(' · ');
}
