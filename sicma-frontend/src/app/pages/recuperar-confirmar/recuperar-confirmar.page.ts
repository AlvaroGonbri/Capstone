import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  IonButton,
  IonContent,
  IonInput,
  IonInputPasswordToggle,
  IonItem,
  IonList,
  IonNote,
  IonSpinner,
  IonText,
} from '@ionic/angular';
import { PasswordResetService } from '../../core/services/password-reset.service';

@Component({
  selector: 'app-recuperar-confirmar',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    IonButton,
    IonContent,
    IonInput,
    IonInputPasswordToggle,
    IonItem,
    IonList,
    IonNote,
    IonSpinner,
    IonText,
  ],
  templateUrl: './recuperar-confirmar.page.html',
  styleUrl: './recuperar-confirmar.page.scss',
})
export class RecuperarConfirmarPage {
  private readonly fb = inject(FormBuilder);
  private readonly ruta = inject(ActivatedRoute);
  private readonly passwordReset = inject(PasswordResetService);

  protected readonly cargando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly actualizado = signal(false);
  protected readonly uid = this.ruta.snapshot.queryParamMap.get('uid') ?? '';
  protected readonly token = this.ruta.snapshot.queryParamMap.get('token') ?? '';

  protected readonly formulario = this.fb.nonNullable.group({
    nuevaClave: ['', [Validators.required, Validators.minLength(8)]],
    confirmarClave: ['', [Validators.required, Validators.minLength(8)]],
  });

  protected enviar(): void {
    if (!this.uid || !this.token) {
      this.error.set('El enlace de recuperación no es válido.');
      return;
    }
    if (this.formulario.invalid || this.cargando()) {
      this.formulario.markAllAsTouched();
      return;
    }

    const { nuevaClave, confirmarClave } = this.formulario.getRawValue();
    if (nuevaClave !== confirmarClave) {
      this.error.set('Las contraseñas no coinciden.');
      return;
    }

    this.cargando.set(true);
    this.error.set(null);
    this.passwordReset.confirmar(this.uid, this.token, nuevaClave).subscribe({
      next: () => {
        this.cargando.set(false);
        this.actualizado.set(true);
      },
      error: (error: { error?: { detail?: string }; message?: string }) => {
        this.cargando.set(false);
        this.error.set(error.error?.detail ?? error.message ?? 'No fue posible actualizar la contraseña.');
      },
    });
  }
}
