import { Component, inject, signal } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { PantallaIngresoComponent } from '../../shared/pantalla-ingreso.component';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  AlertController,
  IonButton,
  IonContent,
  IonIcon,
  IonInput,
  IonInputPasswordToggle,
  IonItem,
  IonList,
  IonNote,
  IonSpinner,
  IonText,
} from '@ionic/angular';
import { addIcons } from 'ionicons';
import { fingerPrintOutline } from 'ionicons/icons';
import { AuthService, DesafioMfa } from '../../core/services/auth.service';
import { BiometriaService } from '../../core/services/biometria.service';

@Component({
  selector: 'app-login',
  imports: [
    NgTemplateOutlet,
    PantallaIngresoComponent,
    ReactiveFormsModule,
    RouterLink,
    IonButton,
    IonContent,
    IonIcon,
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
  private readonly biometria = inject(BiometriaService);
  private readonly alertas = inject(AlertController);

  protected readonly cargando = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Por qué se cerró la sesión anterior (inactividad o un administrador), si fue así. */
  protected readonly aviso = signal<string | null>(null);
  /** App móvil: nombre de quien activó la huella en este teléfono (null = no está activa). */
  protected readonly huella = signal<string | null>(null);

  // ------------------------------------------------- verificación en dos pasos
  private readonly sanitizador = inject(DomSanitizer);
  /** 'credenciales' → ('codigo' | 'configurar') → ('respaldo', solo al terminar de configurar). */
  protected readonly paso = signal<'credenciales' | 'codigo' | 'configurar' | 'respaldo'>('credenciales');
  protected readonly desafio = signal<DesafioMfa | null>(null);
  /** QR de la app de autenticación: SVG generado por el API (en <img> no ejecuta nada). */
  protected readonly qr = signal<SafeUrl | null>(null);
  protected readonly codigosRespaldo = signal<string[]>([]);
  protected readonly copiado = signal(false);
  protected readonly formularioCodigo = this.fb.nonNullable.group({
    codigo: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(20)]],
  });

  protected readonly formulario = this.fb.nonNullable.group({
    identificador: ['', [Validators.required]],
    clave: ['', [Validators.required, Validators.minLength(6)]],
  });

  constructor() {
    addIcons({ fingerPrintOutline });
  }

  /** Cada vez que se muestra el ingreso: si la huella está activa, se pide de inmediato. */
  ionViewDidEnter(): void {
    const motivo = this.ruta.snapshot.queryParamMap.get('sesionExpirada');
    this.aviso.set(
      motivo === 'revocada' ? 'Un administrador cerró tu sesión. Vuelve a iniciar sesión.'
      : motivo === 'inactividad' ? 'Tu sesión se cerró por inactividad.'
      : null,
    );
    this.huella.set(this.biometria.activa());
    if (this.huella() && !this.cargando()) {
      this.entrarConHuella();
    }
  }

  protected entrarConHuella(): void {
    this.cargando.set(true);
    this.error.set(null);
    this.auth.iniciarSesionConHuella().subscribe({
      next: () => {
        this.cargando.set(false);
        this.irAlDestino();
      },
      error: (e: Error & { codigo?: string }) => {
        this.cargando.set(false);
        this.huella.set(this.biometria.activa()); // si la llave ya no sirve, se borró
        if (e.codigo === 'password_expired') {
          void this.router.navigate(['/cambiar-clave'], { queryParams: { motivo: 'expirada' } });
          return;
        }
        if (e.codigo !== 'huella_cancelada') {
          this.error.set(e.message);
        }
      },
    });
  }

  private irAlDestino(): void {
    const destino = this.ruta.snapshot.queryParamMap.get('volverA') ?? '/panel';
    void this.router.navigateByUrl(destino);
  }

  /** Tras entrar con contraseña en la app móvil: ofrece activar la huella (o renueva la llave). */
  private async ofrecerHuella(): Promise<void> {
    const llave = this.auth.tomarLlavePendiente();
    const nombre = this.auth.usuario()?.nombre;
    if (!llave || !nombre || !(await this.biometria.disponible())) {
      return;
    }
    if (this.biometria.activa() === nombre) {
      // Ya la usaba y la llave venció (7 días): se renueva sin preguntar.
      await this.biometria.guardar(llave, nombre).catch(() => undefined);
      return;
    }
    const alerta = await this.alertas.create({
      header: 'Entrar con huella',
      message:
        '¿Quieres entrar con tu huella o el PIN del teléfono la próxima vez? ' +
        'Cada 7 días se vuelve a pedir la contraseña. Tu huella no sale del teléfono.',
      buttons: [
        { text: 'Ahora no', role: 'cancel' },
        { text: 'Activar', role: 'confirm' },
      ],
    });
    await alerta.present();
    const { role } = await alerta.onDidDismiss();
    if (role === 'confirm') {
      await this.biometria.guardar(llave, nombre).catch(() => undefined);
    }
  }

  protected enviar(): void {
    if (this.formulario.invalid || this.cargando()) {
      this.formulario.markAllAsTouched();
      return;
    }

    this.cargando.set(true);
    this.error.set(null);

    const { identificador, clave } = this.formulario.getRawValue();
    this.auth.iniciarSesion(identificador, clave).subscribe({
      next: (resultado) => {
        if ('mfa' in resultado) {
          // La cuenta exige verificación en dos pasos: falta el código de la app de autenticación.
          this.cargando.set(false);
          this.desafio.set(resultado);
          this.qr.set(resultado.qr ? this.sanitizador.bypassSecurityTrustUrl(resultado.qr) : null);
          this.formularioCodigo.reset();
          this.paso.set(resultado.mfa);
          return;
        }
        this.finalizar();
      },
      error: (e: Error & { codigo?: string }) => {
        this.cargando.set(false);
        if (e.codigo === 'password_expired') {
          void this.router.navigate(['/cambiar-clave'], {
            queryParams: { usuario: identificador.trim(), motivo: 'expirada' },
          });
          return;
        }
        this.error.set(e.message || 'No fue posible iniciar sesion.');
      },
    });
  }

  /** Tras entrar: en la app móvil se ofrece la huella; después, a la pantalla pedida. */
  private finalizar(): void {
    void this.ofrecerHuella().finally(() => {
      this.cargando.set(false);
      this.irAlDestino();
    });
  }

  protected verificarCodigo(): void {
    const desafio = this.desafio();
    if (!desafio || this.formularioCodigo.invalid || this.cargando()) {
      this.formularioCodigo.markAllAsTouched();
      return;
    }
    this.cargando.set(true);
    this.error.set(null);
    this.auth.verificarCodigo(desafio.mfa_token, this.formularioCodigo.getRawValue().codigo).subscribe({
      next: ({ codigosRespaldo }) => {
        if (codigosRespaldo?.length) {
          // Recién configurada: los códigos de respaldo se muestran una sola vez.
          this.cargando.set(false);
          this.codigosRespaldo.set(codigosRespaldo);
          this.paso.set('respaldo');
          return;
        }
        this.finalizar();
      },
      error: (e: Error & { codigo?: string }) => {
        this.cargando.set(false);
        if (e.codigo === 'mfa_vencido' || e.codigo === 'account_locked') {
          this.volverAlInicio();
        }
        this.error.set(e.message);
      },
    });
  }

  protected continuarTrasRespaldo(): void {
    this.cargando.set(true);
    this.auth.continuarSesionPendiente().subscribe({
      next: () => this.finalizar(),
      error: (e: Error) => {
        this.cargando.set(false);
        this.volverAlInicio();
        this.error.set(e.message);
      },
    });
  }

  protected volverAlInicio(): void {
    this.paso.set('credenciales');
    this.desafio.set(null);
    this.qr.set(null);
    this.formulario.controls.clave.reset();
    this.error.set(null);
  }

  protected async copiar(texto: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(texto);
      this.copiado.set(true);
      setTimeout(() => this.copiado.set(false), 2000);
    } catch {
      /* sin permiso de portapapeles: se puede copiar a mano */
    }
  }
}
