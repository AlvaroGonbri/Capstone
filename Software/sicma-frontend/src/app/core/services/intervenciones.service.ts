import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { EstadoIntervencion, Intervencion, TecnicoAsignable } from '../models';

export interface DatosAsignacion {
  tecnico: number;
  /** ISO 8601. */
  fecha_inicio: string;
  fecha_termino: string;
  activos: number[];
}

/**
 * Intervenciones (RF-INT). Llegan desde Microsoft Forms y la Jefatura las aprueba en Teams
 * (Power Automate avisa a SICMA por correo); aquí se asignan, ejecutan y cierran.
 */
@Injectable({ providedIn: 'root' })
export class IntervencionesService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/intervenciones/`;

  listar(filtros: { estado?: EstadoIntervencion; activo?: number } = {}): Observable<Intervencion[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    const params: Record<string, string> = {};
    if (filtros.estado) {
      params['estado'] = filtros.estado;
    }
    if (filtros.activo) {
      params['activo'] = String(filtros.activo);
    }
    return this.http.get<Intervencion[]>(this.url, { params });
  }

  listarPorActivo(activoId: number): Observable<Intervencion[]> {
    return this.listar({ activo: activoId });
  }

  tecnicos(): Observable<TecnicoAsignable[]> {
    return this.http.get<TecnicoAsignable[]>(`${this.url}tecnicos/`);
  }

  asignar(id: number, datos: DatosAsignacion): Observable<Intervencion> {
    return this.http.post<Intervencion>(`${this.url}${id}/asignar/`, datos);
  }

  iniciar(id: number): Observable<Intervencion> {
    return this.http.post<Intervencion>(`${this.url}${id}/iniciar/`, {});
  }

  cerrar(id: number, exitosa: boolean, observacion: string): Observable<Intervencion> {
    return this.http.post<Intervencion>(`${this.url}${id}/cerrar/`, { exitosa, observacion });
  }

  cancelar(id: number, motivo: string): Observable<Intervencion> {
    return this.http.post<Intervencion>(`${this.url}${id}/cancelar/`, { motivo });
  }
}

/** Estados en que la intervención ya terminó su ciclo. */
export const ESTADOS_CERRADOS: EstadoIntervencion[] = ['Rechazada', 'Ejecutada', 'Fallida', 'Cancelada'];

const ETIQUETAS: Record<EstadoIntervencion, { etiqueta: string; color: string }> = {
  Pendiente: { etiqueta: 'Pendiente de aprobación', color: 'warning' },
  CambiosSolicitados: { etiqueta: 'Cambios solicitados', color: 'warning' },
  Aprobada: { etiqueta: 'Aprobada', color: 'primary' },
  Rechazada: { etiqueta: 'Rechazada', color: 'medium' },
  EnEjecucion: { etiqueta: 'En ejecución', color: 'tertiary' },
  Ejecutada: { etiqueta: 'Ejecutada', color: 'success' },
  Fallida: { etiqueta: 'Fallida', color: 'danger' },
  Cancelada: { etiqueta: 'Cancelada', color: 'medium' },
};

export function etiquetaEstadoIntervencion(estado: EstadoIntervencion): string {
  return ETIQUETAS[estado]?.etiqueta ?? estado;
}

export function colorEstadoIntervencion(estado: EstadoIntervencion): string {
  return ETIQUETAS[estado]?.color ?? 'medium';
}

/** Título corto para listas: "#12 · Rack A1". */
export function tituloIntervencion(i: Intervencion): string {
  return `#${i.id} · ${i.rack || i.objetivo}`;
}
