import { Injectable, inject } from '@angular/core';
import { Observable, map, of } from 'rxjs';
import { Activo } from '../models';
import { ACTIVOS } from '../mock/datos-simulados';

@Injectable({ providedIn: 'root' })
export class ActivosService {
  listar(): Observable<Activo[]> {
    // TODO: activar cuando exista GET /api/activos/ en el backend.
    return of(ACTIVOS);
  }

  obtenerPorId(id: number): Observable<Activo | undefined> {
    return this.listar().pipe(map((activos) => activos.find((a) => a.id === id)));
  }
}
