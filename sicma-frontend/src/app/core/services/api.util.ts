import { HttpClient } from '@angular/common/http';
import { Observable, delay, of } from 'rxjs';
import { environment } from '../../../environments/environment';

/**
 * Devuelve los datos simulados mientras el API no exista, o hace la llamada
 * real cuando `usarDatosSimulados` sea false. Un solo punto de cambio para
 * los cuatro modulos.
 */
export function obtener<T>(http: HttpClient, ruta: string, simulados: T): Observable<T> {
  if (environment.usarDatosSimulados) {
    return of(simulados).pipe(delay(250));
  }
  return http.get<T>(`${environment.apiUrl}/${ruta}`);
}
