import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Activo, Alerta, EventoTecnico, SincronizacionZabbix } from '../models';

const ESTADOS_ZABBIX: Record<string, string> = {
  operativo: 'Operativo',
  'en falla': 'En falla',
  'en mantencion': 'En mantención',
};

/** Estado de un host de Zabbix tal como se muestra: solo la primera letra en mayúscula ("En falla"). */
export function etiquetaEstadoZabbix(estado: string | null | undefined): string {
  const texto = (estado ?? '').trim();
  if (!texto) return '—';
  return ESTADOS_ZABBIX[texto.toLowerCase()] ?? texto.charAt(0).toUpperCase() + texto.slice(1).toLowerCase();
}

@Injectable({ providedIn: 'root' })
export class ActivosService {
  private readonly http = inject(HttpClient);

  listar(): Observable<Activo[]> {
    return this.http.get<Activo[]>(`${environment.apiUrl}/infraestructura/activos/`);
  }

  obtenerPorId(id: number): Observable<Activo | undefined> {
    return this.listar().pipe(map((activos) => activos.find((a) => a.id === id)));
  }

  /** Alertas abiertas registradas desde el webhook de Zabbix (RF-INF-02). */
  alertasAbiertas(): Observable<Alerta[]> {
    return this.http.get<Alerta[]>(`${environment.apiUrl}/alertas/`, { params: { origen: 'Zabbix' } });
  }

  /** Resultado de la última consulta periódica que hace el backend a Zabbix (RF-INF-01). */
  sincronizacion(): Observable<SincronizacionZabbix> {
    return this.http.get<SincronizacionZabbix>(`${environment.apiUrl}/infraestructura/sincronizacion/`);
  }

  /** Historial de problemas del servidor en Zabbix durante los últimos `dias`. */
  eventos(id: number, dias: number): Observable<EventoTecnico[]> {
    return this.http.get<EventoTecnico[]>(
      `${environment.apiUrl}/infraestructura/hosts/${id}/eventos/`,
      { params: { dias } },
    );
  }
}
