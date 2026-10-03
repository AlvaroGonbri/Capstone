import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { EstadoSensor, NivelAmbiental, Sitio, Umbrales } from '../models';
import { SENSORES, UMBRALES } from '../mock/datos-simulados';

interface SensorApi {
  codigo: string;
  ubicacion: {
    sala: string;
    zona: string | null;
    rack: string | null;
    posicion: string | null;
  };
  ultima_medicion: MedicionApi | null;
}

interface MedicionApi {
  temperatura: number | null;
  humedad: number | null;
  fecha_hora_medicion: string;
}

@Injectable({ providedIn: 'root' })
export class MonitoreoService {
  private readonly http = inject(HttpClient);

  /** Ultimo estado conocido de cada sensor de sala. */
  estadoSensores(): Observable<EstadoSensor[]> {
    const umbrales = this.umbralesConfigurados();
    if (environment.usarDatosSimulados) {
      return of(
        SENSORES.map((sensor) => ({
          ...sensor,
          nivel: obtenerNivel(sensor.temperatura, sensor.humedad, umbrales),
        })),
      );
    }

    return this.http
      .get<SensorApi[]>(`${environment.apiUrl}/sensores/`)
      .pipe(
        map((sensores) =>
          sensores
            .filter((sensor) => sensor.ultima_medicion !== null)
            .map((sensor) => this.convertirSensor(sensor, umbrales)),
        ),
      );
  }

  umbrales(): Observable<Umbrales> {
    return of(this.umbralesConfigurados());
  }

  private convertirSensor(sensor: SensorApi, umbrales: Umbrales): EstadoSensor {
    const medicion = sensor.ultima_medicion!;
    const temperatura = medicion.temperatura ?? 0;
    const humedad = medicion.humedad ?? 0;
    const ubicacion = sensor.ubicacion;

    return {
      sensorId: sensor.codigo,
      ubicacion: ubicacion.zona || ubicacion.sala,
      sitio: obtenerSitio(ubicacion.sala),
      rack: ubicacion.rack || 'sin rack',
      temperatura,
      humedad,
      nivel: obtenerNivel(temperatura, humedad, umbrales),
      actualizadoEn: medicion.fecha_hora_medicion,
      historial: [temperatura],
    };
  }

  private umbralesConfigurados(): Umbrales {
    try {
      const guardados = localStorage.getItem('sicma-configuracion-arduinos');
      const configuraciones = guardados
        ? (JSON.parse(guardados) as Record<string, Partial<Umbrales>>)
        : {};
      const configuracion = configuraciones['arduino-01'];
      return {
        ...UMBRALES,
        temperaturaAdvertencia: configuracion?.temperaturaAdvertencia ?? UMBRALES.temperaturaAdvertencia,
        temperaturaCritica: configuracion?.temperaturaCritica ?? UMBRALES.temperaturaCritica,
      };
    } catch {
      return UMBRALES;
    }
  }
}

function obtenerSitio(sala: string): Sitio {
  return /\bB\b/i.test(sala) ? 'B' : 'A';
}

function obtenerNivel(
  temperatura: number,
  humedad: number,
  umbrales: Umbrales,
): NivelAmbiental {
  if (
    temperatura >= umbrales.temperaturaCritica ||
    humedad < umbrales.humedadMinima ||
    humedad > umbrales.humedadMaxima
  ) {
    return 'critico';
  }
  if (temperatura >= umbrales.temperaturaAdvertencia) {
    return 'advertencia';
  }
  return 'normal';
}
