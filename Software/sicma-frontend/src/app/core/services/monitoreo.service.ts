import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin, map, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Alerta,
  ConexionSensor,
  EstadoSensor,
  HistorialSensor,
  RangoHistorial,
  Sitio,
  UmbralZona,
  Umbrales,
  VersionUmbral,
} from '../models';
import { SENSORES, UMBRALES } from '../mock/datos-simulados';
import { evaluarLectura } from './umbrales.util';

interface UbicacionApi {
  id: number;
  sala: string;
  zona: string | null;
  rack: string | null;
  posicion: string | null;
}

interface SensorApi {
  id: number;
  codigo: string;
  ubicacion: UbicacionApi;
  ultima_medicion: MedicionApi | null;
  conexion: ConexionSensor;
}

interface MedicionApi {
  temperatura: number | null;
  humedad: number | null;
  fecha_hora_medicion: string;
}

interface UmbralApi {
  ubicacion: number;
  variable: 'Temperatura' | 'Humedad';
  /** DRF entrega los decimales como texto. */
  valor_minimo: string;
  valor_maximo: string;
  /** Cada cambio de umbral crea una versión nueva (RF-AMB-03). */
  version: number;
}

type UmbralesConVersion = Umbrales & { version: number | null };

interface HistorialApi {
  sensor: { id: number; codigo: string; ubicacion: string };
  rango: RangoHistorial;
  desde: string;
  hasta: string;
  paso_segundos: number;
  umbrales: HistorialSensor['umbrales'];
  puntos: Array<{
    fecha: string;
    lecturas: number;
    temperatura: number | null;
    temperatura_min: number | null;
    temperatura_max: number | null;
    humedad: number | null;
    humedad_min: number | null;
    humedad_max: number | null;
  }>;
}

/** Duración y tramo de cada período, igual que en el backend (solo para los datos simulados). */
const PERIODOS_SIMULADOS: Record<RangoHistorial, { horas: number; pasoSegundos: number }> = {
  '24h': { horas: 24, pasoSegundos: 600 },
  '7d': { horas: 24 * 7, pasoSegundos: 3600 },
  '30d': { horas: 24 * 30, pasoSegundos: 4 * 3600 },
};

interface ResponsablesApi {
  ubicacion: number;
  correos: string[];
}

export type VariableAmbiental = UmbralApi['variable'];

@Injectable({ providedIn: 'root' })
export class MonitoreoService {
  private readonly http = inject(HttpClient);

  /** Ultimo estado conocido de cada sensor, evaluado con los umbrales de su zona. */
  estadoSensores(): Observable<EstadoSensor[]> {
    if (environment.usarDatosSimulados) {
      return of(SENSORES);
    }

    return forkJoin({
      sensores: this.http.get<SensorApi[]>(`${environment.apiUrl}/sensores/`),
      umbrales: this.umbralesVigentes(),
    }).pipe(
      map(({ sensores, umbrales }) =>
        sensores
          .filter((sensor) => sensor.ultima_medicion !== null)
          .map((sensor) => this.convertirSensor(sensor, umbrales.get(sensor.ubicacion.id) ?? null)),
      ),
    );
  }

  /** Todas las zonas con sus umbrales vigentes (las que no tienen quedan en null). */
  umbralesPorZona(): Observable<UmbralZona[]> {
    if (environment.usarDatosSimulados) {
      return of([{ ubicacionId: 1, nombre: 'Sala A · zona demo', ...UMBRALES, version: null, correos: [] }]);
    }

    return forkJoin({
      ubicaciones: this.http.get<UbicacionApi[]>(`${environment.apiUrl}/ubicaciones/`),
      umbrales: this.umbralesVigentes(),
      responsables: this.http.get<ResponsablesApi[]>(`${environment.apiUrl}/alertas/responsables/`),
    }).pipe(
      map(({ ubicaciones, umbrales, responsables }) =>
        ubicaciones.map((ubicacion) => ({
          ubicacionId: ubicacion.id,
          nombre: nombreUbicacion(ubicacion),
          ...(umbrales.get(ubicacion.id) ?? { ...sinUmbrales(), version: null }),
          correos: responsables.find((r) => r.ubicacion === ubicacion.id)?.correos ?? [],
        })),
      ),
    );
  }

  /** Alertas ambientales abiertas, de la más reciente a la más antigua (RF-AMB-04). */
  alertasAbiertas(): Observable<Alerta[]> {
    if (environment.usarDatosSimulados) {
      return of([]);
    }
    return this.http.get<Alerta[]>(`${environment.apiUrl}/alertas/`, { params: { origen: 'IoT' } });
  }

  /** Reemplaza los responsables de alerta de una zona. Solo administradores (el API lo verifica). */
  guardarResponsables(ubicacionId: number, correos: string[]): Observable<ResponsablesApi> {
    return this.http.put<ResponsablesApi>(
      `${environment.apiUrl}/alertas/responsables/${ubicacionId}/`,
      { correos },
    );
  }

  /** Define el rango de una variable en una zona. Solo administradores (el API lo verifica). */
  guardarUmbral(
    ubicacionId: number,
    variable: VariableAmbiental,
    minimo: number,
    maximo: number,
  ): Observable<unknown> {
    return this.http.post(`${environment.apiUrl}/umbrales/`, {
      ubicacion: ubicacionId,
      variable,
      valor_minimo: minimo,
      valor_maximo: maximo,
    });
  }

  /** Todas las versiones de los umbrales de una zona, de la más reciente a la más antigua. */
  historialUmbrales(ubicacionId: number): Observable<VersionUmbral[]> {
    return this.http
      .get<Array<UmbralApi & { vigente_desde: string }>>(`${environment.apiUrl}/umbrales/`, {
        params: { ubicacion: ubicacionId, historial: true },
      })
      .pipe(
        map((lista) =>
          lista.map((u) => ({
            variable: u.variable,
            minimo: Number(u.valor_minimo),
            maximo: Number(u.valor_maximo),
            version: u.version,
            vigenteDesde: u.vigente_desde,
          })),
        ),
      );
  }

  /**
   * Lecturas de un sensor promediadas por tramo, para el gráfico de temperatura y humedad.
   * Los tramos sin lecturas no vienen: el gráfico los muestra como "sin datos".
   */
  historialSensor(sensorId: number, rango: RangoHistorial): Observable<HistorialSensor> {
    if (environment.usarDatosSimulados) {
      return of(historialSimulado(sensorId, rango));
    }
    return this.http
      .get<HistorialApi>(`${environment.apiUrl}/sensores/${sensorId}/historial/`, { params: { rango } })
      .pipe(
        map((h) => ({
          sensorId: h.sensor.id,
          codigo: h.sensor.codigo,
          ubicacion: h.sensor.ubicacion,
          rango: h.rango,
          desde: h.desde,
          hasta: h.hasta,
          pasoSegundos: h.paso_segundos,
          umbrales: h.umbrales,
          puntos: h.puntos.map((p) => ({
            fecha: p.fecha,
            lecturas: p.lecturas,
            temperatura: p.temperatura,
            temperaturaMin: p.temperatura_min,
            temperaturaMax: p.temperatura_max,
            humedad: p.humedad,
            humedadMin: p.humedad_min,
            humedadMax: p.humedad_max,
          })),
        })),
      );
  }

  /** Umbrales vigentes por zona; la versión es la mayor entre temperatura y humedad. */
  private umbralesVigentes(): Observable<Map<number, UmbralesConVersion>> {
    return this.http.get<UmbralApi[]>(`${environment.apiUrl}/umbrales/`).pipe(
      map((lista) => {
        const porZona = new Map<number, UmbralesConVersion>();
        for (const umbral of lista) {
          const zona = porZona.get(umbral.ubicacion) ?? { ...sinUmbrales(), version: null };
          zona.version = Math.max(zona.version ?? 0, umbral.version ?? 0) || null;
          const minimo = Number(umbral.valor_minimo);
          const maximo = Number(umbral.valor_maximo);
          if (umbral.variable === 'Temperatura') {
            zona.temperaturaMinima = minimo;
            zona.temperaturaMaxima = maximo;
          } else {
            zona.humedadMinima = minimo;
            zona.humedadMaxima = maximo;
          }
          porZona.set(umbral.ubicacion, zona);
        }
        return porZona;
      }),
    );
  }

  private convertirSensor(sensor: SensorApi, umbrales: Umbrales | null): EstadoSensor {
    const medicion = sensor.ultima_medicion!;
    const temperatura = Number(medicion.temperatura ?? 0);
    const humedad = Number(medicion.humedad ?? 0);
    const ubicacion = sensor.ubicacion;

    return {
      id: sensor.id,
      sensorId: sensor.codigo,
      conexion: sensor.conexion,
      ubicacion: ubicacion.zona || ubicacion.sala,
      sitio: obtenerSitio(ubicacion.sala),
      rack: ubicacion.rack || 'sin rack',
      temperatura,
      humedad,
      ...evaluarLectura(temperatura, humedad, umbrales),
      umbrales,
      actualizadoEn: medicion.fecha_hora_medicion,
    };
  }
}

/** Serie de prueba para el modo sin backend: una oscilación diaria con un corte de 6 horas. */
function historialSimulado(sensorId: number, rango: RangoHistorial): HistorialSensor {
  const { horas, pasoSegundos } = PERIODOS_SIMULADOS[rango];
  const paso = pasoSegundos * 1000;
  const hasta = Date.now();
  const desde = Math.floor((hasta - horas * 3_600_000) / paso) * paso;
  const corte = [desde + (hasta - desde) * 0.55, desde + (hasta - desde) * 0.55 + 6 * 3_600_000];
  const puntos = [];
  for (let t = desde; t < hasta; t += paso) {
    if (t >= corte[0] && t < corte[1]) {
      continue;
    }
    const ciclo = Math.sin(((t / 3_600_000) % 24) / 24 * 2 * Math.PI);
    const temperatura = Number((22.5 + ciclo * 2.2).toFixed(2));
    const humedad = Number((45 - ciclo * 6).toFixed(2));
    puntos.push({
      fecha: new Date(t).toISOString(),
      lecturas: Math.round(pasoSegundos / 60),
      temperatura,
      temperaturaMin: temperatura - 0.4,
      temperaturaMax: temperatura + 0.4,
      humedad,
      humedadMin: humedad - 1,
      humedadMax: humedad + 1,
    });
  }
  return {
    sensorId,
    codigo: `ESP-S3-${String(sensorId).padStart(4, '0')}`,
    ubicacion: 'Sala A · zona demo',
    rango,
    desde: new Date(desde).toISOString(),
    hasta: new Date(hasta).toISOString(),
    pasoSegundos,
    umbrales: {
      temperatura: { minimo: UMBRALES.temperaturaMinima ?? 18, maximo: UMBRALES.temperaturaMaxima ?? 27 },
      humedad: { minimo: UMBRALES.humedadMinima ?? 35, maximo: UMBRALES.humedadMaxima ?? 60 },
    },
    puntos,
  };
}

function sinUmbrales(): Umbrales {
  return { temperaturaMinima: null, temperaturaMaxima: null, humedadMinima: null, humedadMaxima: null };
}

function nombreUbicacion(ubicacion: UbicacionApi): string {
  return [ubicacion.sala, ubicacion.zona, ubicacion.rack].filter(Boolean).join(' · ');
}

function obtenerSitio(sala: string): Sitio {
  return /\bB\b/i.test(sala) ? 'B' : 'A';
}
