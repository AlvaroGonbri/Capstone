import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

interface PasswordResetResponse {
  detail: string;
}

@Injectable({ providedIn: 'root' })
export class PasswordResetService {
  private readonly http = inject(HttpClient);

  solicitar(email: string): Observable<PasswordResetResponse> {
    return this.http.post<PasswordResetResponse>(
      `${environment.apiUrl}/auth/password-reset/`,
      { email: email.trim() },
    );
  }

  confirmar(uid: string, token: string, newPassword: string): Observable<PasswordResetResponse> {
    return this.http.post<PasswordResetResponse>(
      `${environment.apiUrl}/auth/password-reset/confirm/`,
      { uid, token, new_password: newPassword },
    );
  }
}
