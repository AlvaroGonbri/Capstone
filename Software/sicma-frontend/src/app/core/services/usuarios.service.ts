import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PoliticaContrasenas, RolGestion, UsuarioGestion } from '../models';

export interface DatosUsuario {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password?: string;
  role: RolGestion;
  is_active: boolean;
  inactivity_timeout_minutes: number;
  password_never_expires: boolean;
}

@Injectable({ providedIn: 'root' })
export class UsuariosService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/auth/users/`;
  private readonly urlPolitica = `${environment.apiUrl}/auth/password-policy/`;

  listar(): Observable<UsuarioGestion[]> {
    return this.http.get<UsuarioGestion[]>(this.url);
  }

  crear(datos: DatosUsuario): Observable<UsuarioGestion> {
    return this.http.post<UsuarioGestion>(this.url, datos);
  }

  actualizar(id: number, datos: Partial<DatosUsuario>): Observable<UsuarioGestion> {
    return this.http.patch<UsuarioGestion>(`${this.url}${id}/`, datos);
  }

  obtenerPolitica(): Observable<PoliticaContrasenas> {
    return this.http.get<PoliticaContrasenas>(this.urlPolitica);
  }

  actualizarPolitica(politica: PoliticaContrasenas): Observable<PoliticaContrasenas> {
    return this.http.patch<PoliticaContrasenas>(this.urlPolitica, politica);
  }
}
