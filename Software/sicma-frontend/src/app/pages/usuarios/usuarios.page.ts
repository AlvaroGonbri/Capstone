import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  IonBadge, IonButton, IonContent, IonInput, IonItem, IonLabel, IonList, IonNote,
  IonSelect, IonSelectOption, IonSpinner, IonText, IonToggle,
} from '@ionic/angular';
import { RolGestion, UsuarioGestion } from '../../core/models';
import { AuthService } from '../../core/services/auth.service';
import { DatosUsuario, UsuariosService } from '../../core/services/usuarios.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

@Component({
  selector: 'app-usuarios',
  imports: [
    ReactiveFormsModule, DatePipe, EncabezadoComponent, IonBadge, IonButton, IonContent,
    IonInput, IonItem, IonLabel, IonList, IonNote, IonSelect, IonSelectOption,
    IonSpinner, IonText, IonToggle,
  ],
  templateUrl: './usuarios.page.html',
  styleUrl: './usuarios.page.scss',
})
export class UsuariosPage {
  private readonly fb = inject(FormBuilder);
  private readonly usuariosService = inject(UsuariosService);
  protected readonly usuarios = signal<UsuarioGestion[]>([]);
  protected readonly cargando = signal(true);
  protected readonly guardando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly editando = signal<number | null>(null);
  /** Solo el Administrador Privilegiado gestiona cuentas de administración y la seguridad de las sesiones. */
  protected readonly esPrivilegiado = inject(AuthService).puedeModificar('administradorprivilegiado');
  protected readonly roles: RolGestion[] = (
    ['Administrador', 'AdministradorPrivilegiado', 'Jefatura', 'Tecnico', 'Auditor', 'Contratistas'] as RolGestion[]
  ).filter((r) => this.esPrivilegiado || (r !== 'Administrador' && r !== 'AdministradorPrivilegiado'));

  protected esCuentaAdministracion(usuario: UsuarioGestion): boolean {
    return usuario.rol === 'administrador' || usuario.rol === 'administradorprivilegiado';
  }

  protected puedeEditarCuenta(usuario: UsuarioGestion): boolean {
    return this.esPrivilegiado || !this.esCuentaAdministracion(usuario);
  }
  protected readonly formulario = this.fb.nonNullable.group({
    username: ['', [Validators.required]],
    email: ['', [Validators.email]],
    first_name: [''],
    last_name: [''],
    password: ['', [Validators.minLength(8)]],
    role: ['Tecnico' as RolGestion, [Validators.required]],
    is_active: [true],
    inactivity_timeout_minutes: [15, [Validators.required, Validators.min(1), Validators.max(120)]],
    password_never_expires: [false],
  });

  protected readonly guardandoPolitica = signal(false);
  protected readonly mensajePolitica = signal<string | null>(null);
  protected readonly errorPolitica = signal<string | null>(null);
  protected readonly formularioPolitica = this.fb.nonNullable.group({
    max_age_days: [90, [Validators.required, Validators.min(0), Validators.max(365)]],
  });

  constructor() {
    this.cargar();
    this.cargarPolitica();
    if (!this.esPrivilegiado) {
      this.formulario.controls.inactivity_timeout_minutes.disable();
      this.formulario.controls.password_never_expires.disable();
      this.formularioPolitica.disable();
    }
  }

  protected cargarPolitica(): void {
    this.usuariosService.obtenerPolitica().subscribe({
      next: (politica) => this.formularioPolitica.reset(politica),
      error: () => this.errorPolitica.set('No fue posible cargar la política de contraseñas.'),
    });
  }

  protected guardarPolitica(): void {
    if (this.formularioPolitica.invalid || this.guardandoPolitica()) {
      this.formularioPolitica.markAllAsTouched();
      this.errorPolitica.set('La vigencia debe estar entre 0 (sin expiración) y 365 días.');
      return;
    }
    this.guardandoPolitica.set(true);
    this.errorPolitica.set(null);
    this.mensajePolitica.set(null);
    const politica = { max_age_days: Number(this.formularioPolitica.getRawValue().max_age_days) };
    this.usuariosService.actualizarPolitica(politica).subscribe({
      next: (guardada) => {
        this.guardandoPolitica.set(false);
        this.formularioPolitica.reset(guardada);
        this.mensajePolitica.set('Política guardada.');
        this.cargar(); // las fechas de vencimiento de la lista cambian con la política
      },
      error: (error: { error?: Record<string, string | string[]> }) => {
        this.guardandoPolitica.set(false);
        this.errorPolitica.set(this.mensajeError(error.error));
      },
    });
  }

  protected cargar(): void {
    this.usuariosService.listar().subscribe({
      next: (usuarios) => { this.usuarios.set(usuarios); this.cargando.set(false); },
      error: (error: { error?: { detail?: string } }) => {
        this.error.set(error.error?.detail ?? 'No fue posible cargar los usuarios.');
        this.cargando.set(false);
      },
    });
  }

  protected nuevo(): void {
    this.editando.set(null);
    this.formulario.reset({
      username: '', email: '', first_name: '', last_name: '', password: '',
      role: 'Tecnico', is_active: true, inactivity_timeout_minutes: 15,
      password_never_expires: false,
    });
    this.error.set(null);
  }

  protected editar(usuario: UsuarioGestion): void {
    if (!this.puedeEditarCuenta(usuario)) {
      this.error.set('Solo un Administrador Privilegiado puede modificar cuentas de administración.');
      return;
    }
    this.editando.set(usuario.id);
    this.formulario.reset({
      username: usuario.username, email: usuario.email, first_name: usuario.first_name,
      last_name: usuario.last_name, password: '', role: this.rolFormulario(usuario),
      is_active: usuario.is_active, inactivity_timeout_minutes: usuario.inactivity_timeout_minutes,
      password_never_expires: usuario.password_never_expires,
    });
    this.error.set(null);
  }

  protected guardar(): void {
    if (this.formulario.invalid || this.guardando()) {
      this.formulario.markAllAsTouched();
      return;
    }
    this.guardando.set(true);
    this.error.set(null);
    const datos = this.formulario.getRawValue() as DatosUsuario;
    if (this.editando() && !datos.password) {
      delete datos.password;
    }
    const operacion = this.editando()
      ? this.usuariosService.actualizar(this.editando()!, datos)
      : this.usuariosService.crear(datos);
    operacion.subscribe({
      next: (usuario) => {
        this.usuarios.update((lista) => {
          const existe = lista.some((item) => item.id === usuario.id);
          return existe ? lista.map((item) => item.id === usuario.id ? usuario : item) : [...lista, usuario];
        });
        this.guardando.set(false);
        this.nuevo();
      },
      error: (error: { error?: Record<string, string | string[]> }) => {
        this.guardando.set(false);
        this.error.set(this.mensajeError(error.error));
      },
    });
  }

  private mensajeError(respuesta?: Record<string, string | string[]>): string {
    if (!respuesta) {
      return 'No fue posible guardar el usuario.';
    }
    if (typeof respuesta['detail'] === 'string') {
      return respuesta['detail'];
    }
    const [campo, mensajes] = Object.entries(respuesta)[0] ?? [];
    const mensaje = Array.isArray(mensajes) ? mensajes[0] : mensajes;
    return campo && mensaje
      ? `${campo}: ${mensaje}`
      : 'No fue posible guardar el usuario.';
  }

  private rolFormulario(usuario: UsuarioGestion): RolGestion {
    const roles: Record<string, RolGestion> = {
      administrador: 'Administrador',
      administradorprivilegiado: 'AdministradorPrivilegiado',
      auditor: 'Auditor',
      jefatura: 'Jefatura',
      tecnico: 'Tecnico',
      contratistas: 'Contratistas',
    };
    return usuario.rol ? (roles[usuario.rol] ?? 'Tecnico') : 'Tecnico';
  }
}
