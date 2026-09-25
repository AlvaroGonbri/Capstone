import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { Intervencion } from '../models';
import { INTERVENCIONES } from '../mock/datos-simulados';
import { obtener } from './api.util';

@Injectable({ providedIn: 'root' })
export class IntervencionesService {
  private readonly http = inject(HttpClient);

  listar(): Observable<Intervencion[]> {
    return obtener(this.http, 'intervenciones/', INTERVENCIONES);
  }

  listarPorActivo(activoId: number): Observable<Intervencion[]> {
    return this.listar().pipe(map((lista) => lista.filter((i) => i.activoId === activoId)));
  }
}
