import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Alerta } from '../models';

/** Gestión manual de alertas: el Técnico o el Administrador las reconoce o cierra (queda quién y cuándo). */
@Injectable({ providedIn: 'root' })
export class AlertasService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.apiUrl}/alertas/`;

  /** "Lo estoy viendo": pasa de Nueva a Reconocida. */
  reconocer(id: number, comentario = ''): Observable<Alerta> {
    return this.http.post<Alerta>(`${this.url}${id}/reconocer/`, { comentario });
  }

  /** Cierra la alerta. Si la condición sigue, la siguiente lectura o evento abre otra. */
  cerrar(id: number, comentario = ''): Observable<Alerta> {
    return this.http.post<Alerta>(`${this.url}${id}/cerrar/`, { comentario });
  }
}
