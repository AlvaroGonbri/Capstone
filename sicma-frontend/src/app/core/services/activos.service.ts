import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { Activo } from '../models';
import { ACTIVOS } from '../mock/datos-simulados';
import { obtener } from './api.util';

@Injectable({ providedIn: 'root' })
export class ActivosService {
  private readonly http = inject(HttpClient);

  listar(): Observable<Activo[]> {
    return obtener(this.http, 'activos/', ACTIVOS);
  }

  obtenerPorId(id: number): Observable<Activo | undefined> {
    return this.listar().pipe(map((activos) => activos.find((a) => a.id === id)));
  }
}
