import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
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
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
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
  templateUrl: './login.page.html',
  styleUrl: './login.page.scss',
})
export class LoginPage {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  private readonly auth = inject(AuthService);

  protected readonly cargando = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly formulario = this.fb.nonNullable.group({
    correo: ['admin@sicma.cl', [Validators.required, Validators.email]],
    clave: ['sicma2026', [Validators.required, Validators.minLength(6)]],
  });

  protected enviar(): void {
    if (this.formulario.invalid || this.cargando()) {
      this.formulario.markAllAsTouched();
      return;
    }

    this.cargando.set(true);
    this.error.set(null);

    const { correo, clave } = this.formulario.getRawValue();
    this.auth.iniciarSesion(correo, clave).subscribe({
      next: () => {
        this.cargando.set(false);
        const destino = this.ruta.snapshot.queryParamMap.get('volverA') ?? '/panel';
        void this.router.navigateByUrl(destino);
      },
      error: (e: Error) => {
        this.cargando.set(false);
        this.error.set(e.message || 'No fue posible iniciar sesion.');
      },
    });
  }
}
