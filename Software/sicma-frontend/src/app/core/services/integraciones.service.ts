import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, delay, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  EstadoIntegraciones,
  NombrePrueba,
  NombreSecreto,
  ResultadoPrueba,
  SecretoRenovado,
} from '../models';

/**
 * Vista Integraciones: estado, comprobaciones en vivo y renovación de los dos secretos que genera
 * SICMA. La renovación va a /api/integraciones/, que el túnel no publica: solo desde la red local.
 */
@Injectable({ providedIn: 'root' })
export class IntegracionesService {
  private readonly http = inject(HttpClient);
  private readonly api = environment.apiUrl;

  estado(): Observable<EstadoIntegraciones> {
    if (environment.usarDatosSimulados) {
      return of(estadoSimulado()).pipe(delay(250));
    }
    return this.http.get<EstadoIntegraciones>(`${this.api}/sistema/integraciones/`);
  }

  probar(nombre: NombrePrueba): Observable<ResultadoPrueba> {
    if (environment.usarDatosSimulados) {
      const detalle = 'Modo de datos simulados: no se probó la conexión real.';
      return of({ ok: true, detalle, probado_en: new Date().toISOString() }).pipe(delay(400));
    }
    return this.http.post<ResultadoPrueba>(`${this.api}/sistema/integraciones/${nombre}/probar/`, {});
  }

  renovar(nombre: NombreSecreto, password: string, inmediato: boolean): Observable<SecretoRenovado> {
    if (environment.usarDatosSimulados) {
      const ahora = Date.now();
      return of({
        nombre,
        secreto: `simulado-${crypto.randomUUID()}`,
        renovado_en: new Date(ahora).toISOString(),
        anterior_valido_hasta: inmediato ? null : new Date(ahora + 24 * 3600_000).toISOString(),
      }).pipe(delay(400));
    }
    return this.http.post<SecretoRenovado>(`${this.api}/integraciones/secretos/${nombre}/renovar/`, {
      password,
      inmediato,
    });
  }
}

function estadoSimulado(): EstadoIntegraciones {
  const hace = (s: number) => new Date(Date.now() - s * 1000).toISOString();
  const sinRenovar = { configurado: true, origen: 'env' as const, renovado_en: null, renovado_por: null, anterior_valido_hasta: null };
  const buzon = { clave: 'procesar_intervenciones', nombre: 'Lectura del buzón de intervenciones', ultima_actividad: hace(25), intervalo_segundos: 60, activo: true, error: null };
  return {
    generado: hace(0),
    red_local: true,
    puede_renovar: true,
    gracia_horas: 24,
    zabbix: { configurado: true, ultimo_intento: hace(40), ultima_exitosa: hace(40), al_dia: true, error: null },
    webhook: { secreto: sinRenovar, ultimo_aviso: hace(7200), rechazos: 0, ultimo_rechazo: null },
    correo: { configurado: true, cuenta: 'si•••@gmail.com' },
    buzon: { configurado: true, secreto: sinRenovar, proceso: buzon, ultimo_correo: hace(86400), descartados: 0, ultimo_descarte: null, detalle_descarte: null },
    tunel: { host: 'api.sicma.cl' },
    gemini: { configurado: false, modelo: 'gemini-3.5-flash', ultimo_resumen: null, error: null },
    procesos: [
      { clave: 'sincronizar_zabbix', nombre: 'Sincronización de Zabbix', ultima_actividad: hace(40), intervalo_segundos: 60, activo: true, error: null },
      buzon,
    ],
    sensores: { en_linea: 2, sin_datos: 1, inactivos: 0 },
    lectores: [{ id: 1, nombre: 'Puerta sala principal', estado: 'Activo', ultimo_contacto: hace(5), en_linea: true }],
    renovaciones: [],
  };
}
