import { HttpClient } from '@angular/common/http';
import { Injectable, effect, inject, signal } from '@angular/core';
import { catchError, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Alerta, ConexionSensor, Intervencion, SincronizacionZabbix } from '../models';
import { AuthService } from './auth.service';
import { ESTADOS_CERRADOS } from './intervenciones.service';

/** Cada cuánto se renueva el estado que muestran el menú y la barra superior. */
const INTERVALO_MS = 30_000;

/**
 * Estado resumido para el menú lateral (contadores) y la barra superior ("Zabbix · hace X s").
 * Se consulta cada 30 s mientras hay sesión, solo con la pestaña visible, y se limpia al salir.
 * Si una consulta falla, ese dato queda sin mostrar: nunca bloquea la navegación.
 */
@Injectable({ providedIn: 'root' })
export class EstadoGeneralService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private temporizador: ReturnType<typeof setInterval> | null = null;

  /** Intervenciones abiertas que el usuario puede ver (el técnico, solo las suyas). */
  readonly intervencionesAbiertas = signal<number | null>(null);
  /** Alertas de infraestructura (Zabbix) abiertas. */
  readonly alertasZabbix = signal<number | null>(null);
  /** Hay algo que revisar en Monitoreo: una alerta ambiental abierta o un sensor sin datos. */
  readonly avisoMonitoreo = signal(false);
  /** Última consulta del backend a Zabbix (RF-INF-01); null si no se pudo saber. */
  readonly sincronizacion = signal<SincronizacionZabbix | null>(null);

  constructor() {
    effect(() => {
      // El Departamento de contratistas solo ve Personal externo: no consulta el resto.
      const activo = this.auth.autenticado() && !this.auth.tieneRol('contratistas');
      if (activo) {
        this.iniciar();
      } else {
        this.detener();
      }
    });
  }

  private iniciar(): void {
    if (this.temporizador) {
      return;
    }
    this.actualizar();
    this.temporizador = setInterval(() => {
      if (!document.hidden) {
        this.actualizar();
      }
    }, INTERVALO_MS);
  }

  private detener(): void {
    if (this.temporizador) {
      clearInterval(this.temporizador);
      this.temporizador = null;
    }
    this.intervencionesAbiertas.set(null);
    this.alertasZabbix.set(null);
    this.avisoMonitoreo.set(false);
    this.sincronizacion.set(null);
  }

  private actualizar(): void {
    const api = environment.apiUrl;

    this.http
      .get<SincronizacionZabbix | null>(`${api}/infraestructura/sincronizacion/`)
      .pipe(catchError(() => of(null)))
      .subscribe((estado) => this.sincronizacion.set(estado));

    this.http
      .get<Intervencion[] | null>(`${api}/intervenciones/`)
      .pipe(catchError(() => of(null)))
      .subscribe((lista) =>
        this.intervencionesAbiertas.set(lista ? lista.filter((i) => !ESTADOS_CERRADOS.includes(i.estado)).length : null),
      );

    this.http
      .get<Alerta[] | null>(`${api}/alertas/`)
      .pipe(catchError(() => of(null)))
      .subscribe((alertas) => {
        this.alertasZabbix.set(alertas ? alertas.filter((a) => a.origen === 'Zabbix').length : null);
        const ambientales = (alertas ?? []).some((a) => a.origen === 'IoT');
        this.http
          .get<Array<{ conexion: ConexionSensor }>>(`${api}/sensores/`)
          .pipe(catchError(() => of([] as Array<{ conexion: ConexionSensor }>)))
          .subscribe((sensores) => this.avisoMonitoreo.set(ambientales || sensores.some((s) => s.conexion === 'Sin datos')));
      });
  }
}
