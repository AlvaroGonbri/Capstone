import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { RolGestion, UsuarioGestion } from '../models';

export interface DatosUsuario {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password?: string;
  role: RolGestion;
  is_active: boolean;
  inactivity_timeout_minutes: number;
}

@Injectable({ providedIn: 'root' })
export class UsuariosService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/auth/users/`;

  listar(): Observable<UsuarioGestion[]> {
    return this.http.get<UsuarioGestion[]>(this.url);
  }

  crear(datos: DatosUsuario): Observable<UsuarioGestion> {
    return this.http.post<UsuarioGestion>(this.url, datos);
  }

  actualizar(id: number, datos: Partial<DatosUsuario>): Observable<UsuarioGestion> {
    return this.http.patch<UsuarioGestion>(`${this.url}${id}/`, datos);
  }
}
