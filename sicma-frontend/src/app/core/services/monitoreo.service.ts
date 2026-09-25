import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { EstadoSensor, Umbrales } from '../models';
import { SENSORES, UMBRALES } from '../mock/datos-simulados';
import { obtener } from './api.util';

@Injectable({ providedIn: 'root' })
export class MonitoreoService {
  private readonly http = inject(HttpClient);

  /** Ultimo estado conocido de cada sensor de sala. */
  estadoSensores(): Observable<EstadoSensor[]> {
    return obtener(this.http, 'monitoreo/sensores/', SENSORES);
  }

  umbrales(): Observable<Umbrales> {
    return obtener(this.http, 'monitoreo/umbrales/', UMBRALES);
  }
}
