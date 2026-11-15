import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, delay, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { FiltroReporte, ReportePeriodo } from '../models';

/** Reportes del período (inteligencia de negocio): cifras, resumen y PDF generado en el servidor. */
@Injectable({ providedIn: 'root' })
export class ReportesService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/reportes/`;

  resumen(filtro: FiltroReporte = {}): Observable<ReportePeriodo> {
    if (environment.usarDatosSimulados) {
      return of(reporteSimulado(filtro)).pipe(delay(300));
    }
    return this.http.get<ReportePeriodo>(`${this.url}resumen/`, { params: parametros(filtro) });
  }

  pdf(filtro: FiltroReporte): Observable<Blob> {
    return this.http.get(`${this.url}pdf/`, { params: parametros(filtro), responseType: 'blob' });
  }
}

function parametros(filtro: FiltroReporte): HttpParams {
  let params = new HttpParams();
  if (filtro.desde) params = params.set('desde', filtro.desde);
  if (filtro.hasta) params = params.set('hasta', filtro.hasta);
  if (filtro.zona) params = params.set('zona', filtro.zona);
  return params;
}

function reporteSimulado(filtro: FiltroReporte): ReportePeriodo {
  const hasta = filtro.hasta ?? new Date().toISOString().slice(0, 10);
  const desde = filtro.desde ?? hasta;
  return {
    periodo: { desde, hasta, dias: 1, zona: null },
    disponibilidad: { porcentaje: 99.4, hosts: [], por_dia: [{ fecha: hasta, porcentaje: 99.4 }], error: null },
    ambiente: {
      lecturas: 1440,
      temperatura: { promedio: 22.4, minimo: 19.8, maximo: 26.1 },
      humedad: { promedio: 45, minimo: 38, maximo: 55 },
    },
    alertas_ambientales: { total: 2, por_severidad: { Advertencia: 2 }, abiertas_al_cierre: 0, resolucion_promedio_min: 14, resolucion_con_datos: 2 },
    problemas_zabbix: { total: 3, por_severidad: { Alta: 1, Advertencia: 2 }, altos_o_criticos: 1, abiertos_al_cierre: 1 },
    intervenciones: { total: 3, por_estado: { Ejecutada: 2, Aprobada: 1 }, cerradas: 2, abiertas: 1 },
    accesos: { permitidos: 42, denegados: 3, fallas_del_lector: 0 },
    eventos: [],
    resumen: {
      texto: 'Modo de datos simulados: este resumen no proviene del backend.',
      origen: 'plantilla',
      modelo: null,
      motivo: null,
    },
  };
}
