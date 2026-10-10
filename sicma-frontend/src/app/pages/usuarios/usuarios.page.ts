import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  IonBadge, IonButton, IonContent, IonInput, IonItem, IonLabel, IonList,
  IonSelect, IonSelectOption, IonSpinner, IonText,
} from '@ionic/angular';
import { RolGestion, UsuarioGestion } from '../../core/models';
import { DatosUsuario, UsuariosService } from '../../core/services/usuarios.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

@Component({
  selector: 'app-usuarios',
  imports: [
    ReactiveFormsModule, EncabezadoComponent, IonBadge, IonButton, IonContent,
    IonInput, IonItem, IonLabel, IonList, IonSelect, IonSelectOption,
    IonSpinner, IonText,
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
  protected readonly roles: RolGestion[] = [
    'Administrador', 'AdministradorPrivilegiado', 'Jefatura', 'Tecnico', 'Auditor',
  ];
  protected readonly formulario = this.fb.nonNullable.group({
    username: ['', [Validators.required]],
    email: ['', [Validators.email]],
    first_name: [''],
    last_name: [''],
    password: ['', [Validators.minLength(8)]],
    role: ['Tecnico' as RolGestion, [Validators.required]],
    is_active: [true],
    inactivity_timeout_minutes: [15, [Validators.required, Validators.min(1), Validators.max(120)]],
  });

  constructor() {
    this.cargar();
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
    });
    this.error.set(null);
  }

  protected editar(usuario: UsuarioGestion): void {
    this.editando.set(usuario.id);
    this.formulario.reset({
      username: usuario.username, email: usuario.email, first_name: usuario.first_name,
      last_name: usuario.last_name, password: '', role: this.rolFormulario(usuario),
      is_active: usuario.is_active, inactivity_timeout_minutes: usuario.inactivity_timeout_minutes,
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
      error: (error: { error?: { detail?: string; password?: string[] } }) => {
        this.guardando.set(false);
        this.error.set(error.error?.detail ?? error.error?.password?.[0] ?? 'No fue posible guardar el usuario.');
      },
    });
  }

  private rolFormulario(usuario: UsuarioGestion): RolGestion {
    const roles: Record<string, RolGestion> = {
      administrador: 'Administrador',
      auditor: 'Auditor',
      jefatura: 'Jefatura',
      tecnico: 'Tecnico',
    };
    return usuario.rol ? (roles[usuario.rol] ?? 'Tecnico') : 'Tecnico';
  }
}
