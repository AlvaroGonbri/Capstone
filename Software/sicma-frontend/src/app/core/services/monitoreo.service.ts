import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin, map, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Alerta, EstadoSensor, Sitio, UmbralZona, Umbrales } from '../models';
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
  codigo: string;
  ubicacion: UbicacionApi;
  ultima_medicion: MedicionApi | null;
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
}

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
      return of([{ ubicacionId: 1, nombre: 'Sala A · zona demo', ...UMBRALES, correos: [] }]);
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
          ...(umbrales.get(ubicacion.id) ?? sinUmbrales()),
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

  private umbralesVigentes(): Observable<Map<number, Umbrales>> {
    return this.http.get<UmbralApi[]>(`${environment.apiUrl}/umbrales/`).pipe(
      map((lista) => {
        const porZona = new Map<number, Umbrales>();
        for (const umbral of lista) {
          const zona = porZona.get(umbral.ubicacion) ?? sinUmbrales();
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
      sensorId: sensor.codigo,
      ubicacion: ubicacion.zona || ubicacion.sala,
      sitio: obtenerSitio(ubicacion.sala),
      rack: ubicacion.rack || 'sin rack',
      temperatura,
      humedad,
      ...evaluarLectura(temperatura, humedad, umbrales),
      umbrales,
      actualizadoEn: medicion.fecha_hora_medicion,
      historial: [temperatura],
    };
  }
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
