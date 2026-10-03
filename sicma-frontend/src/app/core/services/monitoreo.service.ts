import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { EstadoSensor, Umbrales } from '../models';
import { SENSORES, UMBRALES } from '../mock/datos-simulados';

@Injectable({ providedIn: 'root' })
export class MonitoreoService {
  /** Ultimo estado conocido de cada sensor de sala. */
  estadoSensores(): Observable<EstadoSensor[]> {
    // TODO: adaptar al contrato GET /api/sensores/ antes de activar la API.
    return of(SENSORES);
  }

  umbrales(): Observable<Umbrales> {
    // TODO: adaptar al contrato GET /api/umbrales/?ubicacion=... antes de activarlo.
    return of(UMBRALES);
  }
}
