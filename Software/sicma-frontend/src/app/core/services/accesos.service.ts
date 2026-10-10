import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { Acceso } from '../models';
import { ACCESOS } from '../mock/datos-simulados';

@Injectable({ providedIn: 'root' })
export class AccesosService {
  listar(): Observable<Acceso[]> {
    // TODO: activar cuando exista GET /api/accesos/ en el backend.
    return of(ACCESOS);
  }
}
