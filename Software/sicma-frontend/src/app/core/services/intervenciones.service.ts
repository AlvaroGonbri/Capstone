import { Injectable } from '@angular/core';
import { Observable, map, of } from 'rxjs';
import { Intervencion } from '../models';
import { INTERVENCIONES } from '../mock/datos-simulados';

@Injectable({ providedIn: 'root' })
export class IntervencionesService {
  listar(): Observable<Intervencion[]> {
    // TODO: activar cuando exista GET /api/intervenciones/ en el backend.
    return of(INTERVENCIONES);
  }

  listarPorActivo(activoId: number): Observable<Intervencion[]> {
    return this.listar().pipe(map((lista) => lista.filter((i) => i.activoId === activoId)));
  }
}
