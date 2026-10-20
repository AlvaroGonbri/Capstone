import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, of, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  ActivoInventario,
  Criticidad,
  EstadoActivoCatalogo,
  EstadoInventario,
  HistorialActivo,
  TipoActivoCatalogo,
  UsuarioResumen,
} from '../models';

export interface FiltrosActivos {
  q?: string;
  tipo?: string;
  ubicacion?: number;
  estado?: EstadoInventario;
  incluir_retirados?: boolean;
}

export interface DatosActivo {
  codigo: string;
  nombre: string;
  tipo: string | null;
  marca: string | null;
  modelo: string | null;
  numero_serie: string;
  estado: EstadoInventario;
  criticidad: Criticidad;
  ubicacion: number;
  responsable: number | null;
  observaciones: string | null;
}

/** Estado de alta de un activo y estado de baja (RN-02); ambos son de sistema en el catálogo. */
export const ESTADO_INICIAL = 'Operativo';
export const ESTADO_RETIRADO = 'Retirado';

/** Inventario de activos (RF-ACT) y catálogos de tipos y estados (RF-CAT-03). */
@Injectable({ providedIn: 'root' })
export class InventarioService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/activos/`;

  /** Catálogo de estados (incluye desactivados, para mostrar bien los activos que los conservan). */
  readonly estadosCatalogo = signal<EstadoActivoCatalogo[]>([]);

  constructor() {
    this.recargarEstados();
  }

  listar(filtros: FiltrosActivos = {}): Observable<ActivoInventario[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    const params: Record<string, string> = {};
    for (const [clave, valor] of Object.entries(filtros)) {
      if (valor !== undefined && valor !== null && valor !== '') {
        params[clave] = String(valor);
      }
    }
    return this.http.get<ActivoInventario[]>(this.url, { params });
  }

  obtener(id: number): Observable<ActivoInventario> {
    return this.http.get<ActivoInventario>(`${this.url}${id}/`);
  }

  crear(datos: DatosActivo): Observable<ActivoInventario> {
    return this.http.post<ActivoInventario>(this.url, datos);
  }

  actualizar(id: number, datos: Partial<DatosActivo>): Observable<ActivoInventario> {
    return this.http.patch<ActivoInventario>(`${this.url}${id}/`, datos);
  }

  historial(id: number): Observable<HistorialActivo[]> {
    return this.http.get<HistorialActivo[]>(`${this.url}${id}/historial/`);
  }

  responsablesPosibles(): Observable<UsuarioResumen[]> {
    return this.http.get<UsuarioResumen[]>(`${this.url}responsables/`);
  }

  tipos(incluirDesactivados = false): Observable<TipoActivoCatalogo[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    return this.http.get<TipoActivoCatalogo[]>(`${this.url}tipos/`, {
      params: incluirDesactivados ? { todos: '1' } : {},
    });
  }

  crearTipo(nombre: string): Observable<TipoActivoCatalogo> {
    return this.http.post<TipoActivoCatalogo>(`${this.url}tipos/`, { nombre });
  }

  estados(): Observable<EstadoActivoCatalogo[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    return this.http
      .get<EstadoActivoCatalogo[]>(`${this.url}estados/`, { params: { todos: '1' } })
      .pipe(tap((lista) => this.estadosCatalogo.set(lista)));
  }

  recargarEstados(): void {
    this.estados().subscribe({ error: () => undefined });
  }

  crearEstado(datos: Pick<EstadoActivoCatalogo, 'nombre' | 'etiqueta' | 'color'>): Observable<EstadoActivoCatalogo> {
    return this.http.post<EstadoActivoCatalogo>(`${this.url}estados/`, datos).pipe(tap(() => this.recargarEstados()));
  }

  actualizarEstado(
    id: number,
    datos: Partial<Pick<EstadoActivoCatalogo, 'etiqueta' | 'color' | 'activo' | 'orden'>>,
  ): Observable<EstadoActivoCatalogo> {
    return this.http.patch<EstadoActivoCatalogo>(`${this.url}estados/${id}/`, datos).pipe(tap(() => this.recargarEstados()));
  }

  /** Estados que se pueden elegir; `actual` se conserva aunque se haya desactivado. */
  estadosSeleccionables(actual?: string | null): EstadoActivoCatalogo[] {
    return this.estadosCatalogo().filter((e) => e.activo || e.nombre === actual);
  }

  etiquetaEstado(estado: EstadoInventario): string {
    return this.estadosCatalogo().find((e) => e.nombre === estado)?.etiqueta ?? estado.replaceAll('_', ' ');
  }

  colorEstado(estado: EstadoInventario): string {
    return this.estadosCatalogo().find((e) => e.nombre === estado)?.color ?? 'medium';
  }

  actualizarTipo(id: number, datos: Partial<Pick<TipoActivoCatalogo, 'nombre' | 'activo'>>): Observable<TipoActivoCatalogo> {
    return this.http.patch<TipoActivoCatalogo>(`${this.url}tipos/${id}/`, datos);
  }
}

export const CRITICIDADES: Criticidad[] = ['Baja', 'Media', 'Alta', 'Critica'];

/** Colores de Ionic que acepta un estado (los mismos que valida el backend). */
export const COLORES_ESTADO = ['primary', 'secondary', 'tertiary', 'success', 'warning', 'danger', 'medium', 'dark'];

/** Primer mensaje de error de una respuesta 400 de DRF, con el nombre del campo. */
export function mensajeErrorApi(respuesta: unknown, porDefecto: string): string {
  if (!respuesta || typeof respuesta !== 'object') {
    return porDefecto;
  }
  const [campo, valor] = Object.entries(respuesta as Record<string, unknown>)[0] ?? [];
  const mensaje = Array.isArray(valor) ? valor[0] : valor;
  if (typeof mensaje !== 'string') {
    return porDefecto;
  }
  return campo === 'detail' || campo === 'non_field_errors' ? mensaje : `${campo}: ${mensaje}`;
}
