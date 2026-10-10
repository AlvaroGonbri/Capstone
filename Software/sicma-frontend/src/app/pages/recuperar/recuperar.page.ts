import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import {
  IonButton,
  IonContent,
  IonInput,
  IonItem,
  IonList,
  IonNote,
  IonSpinner,
  IonText,
} from '@ionic/angular';
import { PasswordResetService } from '../../core/services/password-reset.service';

@Component({
  selector: 'app-recuperar',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    IonButton,
    IonContent,
    IonInput,
    IonItem,
    IonList,
    IonNote,
    IonSpinner,
    IonText,
  ],
  templateUrl: './recuperar.page.html',
  styleUrl: './recuperar.page.scss',
})
export class RecuperarPage {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly passwordReset = inject(PasswordResetService);

  protected readonly cargando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly validacion = signal<string | null>(null);
  protected readonly enviado = signal(false);

  protected readonly formulario = this.fb.nonNullable.group({
    correo: ['', [Validators.required, Validators.email]],
  });

  protected enviar(): void {
    if (this.formulario.invalid || this.cargando()) {
      this.formulario.markAllAsTouched();
      this.validacion.set('Ingresa un correo electrónico válido.');
      return;
    }

    this.cargando.set(true);
    this.error.set(null);
    this.validacion.set(null);
    const { correo } = this.formulario.getRawValue();

    this.passwordReset.solicitar(correo).subscribe({
      next: () => {
        this.cargando.set(false);
        this.enviado.set(true);
      },
      error: (error: { error?: { detail?: string }; message?: string }) => {
        this.cargando.set(false);
        this.error.set(error.error?.detail ?? error.message ?? 'No fue posible procesar la solicitud.');
      },
    });
  }

  protected volverAlLogin(): void {
    void this.router.navigateByUrl('/login');
  }
}
