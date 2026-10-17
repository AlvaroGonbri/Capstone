import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { Arduino, EstadoSensor } from '../models';
import { MonitoreoService } from './monitoreo.service';

@Injectable({ providedIn: 'root' })
export class ArduinosService {
  private readonly monitoreo = inject(MonitoreoService);

  /** Controladores ambientales con su última lectura y los umbrales de su zona. */
  listar(): Observable<Arduino[]> {
    return this.monitoreo.estadoSensores().pipe(
      map((sensores) => sensores.map((sensor) => this.convertirSensor(sensor))),
    );
  }

  private convertirSensor(sensor: EstadoSensor): Arduino {
    return {
      id: sensor.sensorId,
      nombre: 'Nodo de monitoreo ambiental',
      ubicacion: sensor.ubicacion,
      sitio: sensor.sitio,
      rack: sensor.rack,
      estado: 'conectado',
      ultimaLectura: sensor.actualizadoEn,
      temperatura: sensor.temperatura,
      humedad: sensor.humedad,
      umbrales: sensor.umbrales,
    };
  }
}
