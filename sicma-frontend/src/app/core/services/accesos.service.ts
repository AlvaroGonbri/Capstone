import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Acceso } from '../models';
import { ACCESOS } from '../mock/datos-simulados';
import { obtener } from './api.util';

@Injectable({ providedIn: 'root' })
export class AccesosService {
  private readonly http = inject(HttpClient);

  listar(): Observable<Acceso[]> {
    return obtener(this.http, 'accesos/', ACCESOS);
  }
}
