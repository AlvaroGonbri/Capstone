import { Injectable, inject, signal } from '@angular/core';
import { Observable, map, of } from 'rxjs';
import { Arduino } from '../models';
import { MonitoreoService } from './monitoreo.service';

const CLAVE_CONFIGURACION = 'sicma-configuracion-arduinos';

@Injectable({ providedIn: 'root' })
export class ArduinosService {
  private readonly monitoreo = inject(MonitoreoService);
  private readonly datos = signal<Arduino[]>([]);
  private readonly configuraciones = this.cargarConfiguraciones();

  listar(): Observable<Arduino[]> {
    return this.monitoreo.estadoSensores().pipe(
      map((sensores) => {
        const sensor = sensores.find((item) => item.sensorId.toLowerCase() === 'arduino-01') ?? sensores[0];
        const lista = sensor ? [this.convertirSensor(sensor)] : [];
        this.datos.set(lista);
        return lista;
      }),
    );
  }

  actualizarParametros(
    id: string,
    parametros: Pick<Arduino, 'temperaturaMinima' | 'temperaturaAdvertencia' | 'temperaturaCritica'>,
  ): Observable<Arduino> {
    const actual = this.datos().find((arduino) => arduino.id === id);
    if (!actual) {
      throw new Error(`No se encontró el Arduino ${id}.`);
    }

    const actualizado = { ...actual, ...parametros };
    this.datos.update((arduinos) =>
      arduinos.map((arduino) => (arduino.id === id ? actualizado : arduino)),
    );
    this.guardarDatos(this.datos());
    return of(actualizado);
  }

  private convertirSensor(sensor: {
    sensorId: string;
    ubicacion: string;
    sitio: 'A' | 'B';
    rack: string;
    actualizadoEn: string;
    temperatura: number;
  }): Arduino {
    const configuracion = this.configuraciones[sensor.sensorId] ?? {};
    return {
      id: sensor.sensorId,
      nombre: 'Nodo de monitoreo ambiental',
      ubicacion: sensor.ubicacion,
      sitio: sensor.sitio,
      rack: sensor.rack,
      estado: 'conectado',
      ultimaLectura: sensor.actualizadoEn,
      temperatura: sensor.temperatura,
      temperaturaMinima: configuracion.temperaturaMinima ?? 18,
      temperaturaAdvertencia: configuracion.temperaturaAdvertencia ?? 24,
      temperaturaCritica: configuracion.temperaturaCritica ?? 27,
    };
  }

  private cargarConfiguraciones(): Record<string, Partial<Arduino>> {
    try {
      const guardados = localStorage.getItem(CLAVE_CONFIGURACION);
      if (guardados) {
        return JSON.parse(guardados) as Record<string, Partial<Arduino>>;
      }
    } catch {
      // Se usan los valores predeterminados si el almacenamiento no está disponible.
    }
    return {};
  }

  private guardarDatos(arduinos: Arduino[]): void {
    try {
      const configuraciones = Object.fromEntries(
        arduinos.map((arduino) => [
          arduino.id,
          {
            temperaturaMinima: arduino.temperaturaMinima,
            temperaturaAdvertencia: arduino.temperaturaAdvertencia,
            temperaturaCritica: arduino.temperaturaCritica,
          },
        ]),
      );
      localStorage.setItem(CLAVE_CONFIGURACION, JSON.stringify(configuraciones));
    } catch {
      // La configuración permanece activa durante la sesión.
    }
  }
}
