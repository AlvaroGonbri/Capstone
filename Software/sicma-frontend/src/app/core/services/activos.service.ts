import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Activo, Alerta, EventoTecnico, SincronizacionZabbix } from '../models';

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
