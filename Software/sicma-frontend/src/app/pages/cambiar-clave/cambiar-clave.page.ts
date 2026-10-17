import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
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
  selector: 'app-cambiar-clave',
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
  templateUrl: './cambiar-clave.page.html',
  styleUrl: '../recuperar-confirmar/recuperar-confirmar.page.scss',
})
export class CambiarClavePage {
  private readonly fb = inject(FormBuilder);
  private readonly ruta = inject(ActivatedRoute);
  private readonly passwordReset = inject(PasswordResetService);

  protected readonly cargando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly actualizado = signal(false);
  protected readonly expirada = this.ruta.snapshot.queryParamMap.get('motivo') === 'expirada';

  protected readonly formulario = this.fb.nonNullable.group({
    usuario: [this.ruta.snapshot.queryParamMap.get('usuario') ?? '', [Validators.required]],
    claveActual: ['', [Validators.required]],
    nuevaClave: ['', [Validators.required, Validators.minLength(8)]],
    confirmarClave: ['', [Validators.required, Validators.minLength(8)]],
  });

  protected enviar(): void {
    if (this.formulario.invalid || this.cargando()) {
      this.formulario.markAllAsTouched();
      return;
    }

    const { usuario, claveActual, nuevaClave, confirmarClave } = this.formulario.getRawValue();
    if (nuevaClave !== confirmarClave) {
      this.error.set('Las contraseñas nuevas no coinciden.');
      return;
    }

    this.cargando.set(true);
    this.error.set(null);
    this.passwordReset.cambiar(usuario, claveActual, nuevaClave).subscribe({
      next: () => {
        this.cargando.set(false);
        this.actualizado.set(true);
      },
      error: (error: { error?: Record<string, string | string[]> }) => {
        this.cargando.set(false);
        this.error.set(this.mensajeError(error.error));
      },
    });
  }

  private mensajeError(respuesta?: Record<string, string | string[]>): string {
    const mensajes = respuesta?.['detail'] ?? respuesta?.['new_password'];
    const mensaje = Array.isArray(mensajes) ? mensajes[0] : mensajes;
    return mensaje ?? 'No fue posible cambiar la contraseña.';
  }
}
