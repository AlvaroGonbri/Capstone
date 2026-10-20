import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonInput,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSegment,
  IonSegmentButton,
  IonSelect,
  IonSelectOption,
  IonText,
} from '@ionic/angular';
import { Observable } from 'rxjs';
import { EstadoActivoCatalogo, SensorCatalogo, TipoActivoCatalogo, UbicacionCatalogo } from '../../core/models';
import { AuthService } from '../../core/services/auth.service';
import { CatalogosService, nombreUbicacion } from '../../core/services/catalogos.service';
import { COLORES_ESTADO, InventarioService, mensajeErrorApi } from '../../core/services/inventario.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

type Pestana = 'ubicaciones' | 'sensores' | 'tipos' | 'estados';

@Component({
  selector: 'app-catalogos',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    EncabezadoComponent,
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonInput,
    IonItem,
    IonLabel,
    IonList,
    IonNote,
    IonSegment,
    IonSegmentButton,
    IonSelect,
    IonSelectOption,
    IonText,
  ],
  templateUrl: './catalogos.page.html',
  styleUrl: './catalogos.page.scss',
})
export class CatalogosPage {
  private readonly fb = inject(FormBuilder);
  private readonly catalogos = inject(CatalogosService);
  private readonly inventario = inject(InventarioService);

  /** RF-CAT: el Administrador mantiene los catálogos; los demás roles consultan. */
  protected readonly esAdmin = inject(AuthService).puedeModificar('administrador', 'administradorprivilegiado');
  protected readonly pestana = signal<Pestana>('ubicaciones');
  protected readonly mensaje = signal<{ texto: string; error: boolean } | null>(null);
  protected readonly nombreUbicacion = nombreUbicacion;

  protected readonly ubicaciones = signal<UbicacionCatalogo[]>([]);
  protected readonly sensores = signal<SensorCatalogo[]>([]);
  protected readonly tipos = signal<TipoActivoCatalogo[]>([]);
  /** Los no administradores solo ven los estados vigentes. */
  protected readonly estados = computed(() =>
    this.inventario.estadosCatalogo().filter((e) => this.esAdmin || e.activo),
  );
  protected readonly coloresEstado = COLORES_ESTADO;

  /** Clave del dispositivo recién creada o regenerada: se muestra una sola vez. */
  protected readonly claveNueva = signal<{ codigo: string; clave: string } | null>(null);

  protected readonly editandoUbicacion = signal<number | null>(null);
  protected readonly formUbicacion = this.fb.group({
    sala: this.fb.nonNullable.control('', [Validators.required, Validators.maxLength(100)]),
    zona: this.fb.control<string | null>(null),
    rack: this.fb.control<string | null>(null),
    posicion: this.fb.control<string | null>(null),
    ubicacion_padre: this.fb.control<number | null>(null),
  });

  protected readonly editandoSensor = signal<number | null>(null);
  protected readonly formSensor = this.fb.group({
    codigo: this.fb.nonNullable.control('', [Validators.required, Validators.maxLength(50)]),
    tipo: this.fb.nonNullable.control('DHT22', [Validators.required]),
    ubicacion: this.fb.control<number | null>(null, [Validators.required]),
    intervalo_esperado_segundos: this.fb.nonNullable.control(60, [Validators.required, Validators.min(1)]),
  });

  protected readonly formTipo = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(100)]],
  });

  protected readonly formEstado = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(50), Validators.pattern(/^[A-Za-zÁÉÍÓÚÑáéíóúñ0-9_]+$/)]],
    etiqueta: ['', [Validators.maxLength(100)]],
    color: ['medium', [Validators.required]],
  });

  constructor() {
    this.cargar();
  }

  protected cambiarPestana(valor: unknown): void {
    this.pestana.set(valor as Pestana);
    this.mensaje.set(null);
  }

  protected ubicacionesActivas(): UbicacionCatalogo[] {
    return this.ubicaciones().filter((u) => u.activa);
  }

  // ------------------------------------------------------------ Ubicaciones

  protected editarUbicacion(u: UbicacionCatalogo): void {
    this.editandoUbicacion.set(u.id);
    this.formUbicacion.reset({ ...u, ubicacion_padre: u.ubicacion_padre_id });
  }

  protected nuevaUbicacion(): void {
    this.editandoUbicacion.set(null);
    this.formUbicacion.reset({ sala: '', zona: null, rack: null, posicion: null, ubicacion_padre: null });
  }

  protected guardarUbicacion(): void {
    if (this.formUbicacion.invalid) {
      this.formUbicacion.markAllAsTouched();
      return;
    }
    const v = this.formUbicacion.getRawValue();
    const datos = {
      sala: v.sala.trim(), zona: v.zona?.trim() || null, rack: v.rack?.trim() || null,
      posicion: v.posicion?.trim() || null, ubicacion_padre: v.ubicacion_padre,
    };
    const id = this.editandoUbicacion();
    this.ejecutar(
      id ? this.catalogos.actualizarUbicacion(id, datos) : this.catalogos.crearUbicacion({ ...datos, activa: true }),
      id ? 'Ubicación actualizada.' : 'Ubicación creada.',
      () => this.nuevaUbicacion(),
    );
  }

  protected cambiarEstadoUbicacion(u: UbicacionCatalogo): void {
    this.ejecutar(
      this.catalogos.actualizarUbicacion(u.id, { activa: !u.activa }),
      u.activa ? 'Ubicación desactivada.' : 'Ubicación reactivada.',
    );
  }

  // ------------------------------------------------------- Dispositivos IoT

  protected editarSensor(s: SensorCatalogo): void {
    this.editandoSensor.set(s.id);
    this.claveNueva.set(null);
    this.formSensor.reset({ ...s, ubicacion: s.ubicacion.id });
    this.formSensor.controls.codigo.disable(); // el dispositivo se identifica con su código
  }

  protected nuevoSensor(): void {
    this.editandoSensor.set(null);
    this.formSensor.reset({ codigo: '', tipo: 'DHT22', ubicacion: null, intervalo_esperado_segundos: 60 });
    this.formSensor.controls.codigo.enable();
  }

  protected guardarSensor(): void {
    if (this.formSensor.invalid) {
      this.formSensor.markAllAsTouched();
      return;
    }
    const v = this.formSensor.getRawValue();
    const id = this.editandoSensor();
    if (id) {
      const { codigo: _codigo, ...cambios } = v;
      this.ejecutar(
        this.catalogos.actualizarSensor(id, { ...cambios, ubicacion: cambios.ubicacion!, tipo: cambios.tipo.trim() }),
        'Dispositivo actualizado.',
        () => this.nuevoSensor(),
      );
      return;
    }
    this.mensaje.set(null);
    this.catalogos.crearSensor({ ...v, codigo: v.codigo.trim(), ubicacion: v.ubicacion!, estado: 'Activo' }).subscribe({
      next: (creado) => {
        this.claveNueva.set({ codigo: creado.codigo, clave: creado.clave_dispositivo });
        this.mensaje.set({ texto: 'Dispositivo registrado.', error: false });
        this.nuevoSensor();
        this.cargar();
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible registrar el dispositivo.'), error: true }),
    });
  }

  protected cambiarEstadoSensor(s: SensorCatalogo): void {
    this.ejecutar(
      this.catalogos.actualizarSensor(s.id, { estado: s.estado === 'Activo' ? 'Inactivo' : 'Activo' }),
      s.estado === 'Activo' ? 'Dispositivo desactivado: sus lecturas se rechazarán.' : 'Dispositivo reactivado.',
    );
  }

  protected regenerarClave(s: SensorCatalogo): void {
    if (!confirm(`¿Generar una clave nueva para ${s.codigo}? La actual dejará de funcionar de inmediato.`)) {
      return;
    }
    this.catalogos.regenerarClave(s.id).subscribe({
      next: ({ codigo, clave_dispositivo }) => this.claveNueva.set({ codigo, clave: clave_dispositivo }),
      error: () => this.mensaje.set({ texto: 'No fue posible generar la clave.', error: true }),
    });
  }

  // -------------------------------------------------------- Tipos de activo

  protected crearTipo(): void {
    if (this.formTipo.invalid) {
      return;
    }
    this.ejecutar(
      this.inventario.crearTipo(this.formTipo.getRawValue().nombre.trim()),
      'Tipo creado.',
      () => this.formTipo.reset(),
    );
  }

  protected renombrarTipo(t: TipoActivoCatalogo, nombre: string | null | undefined): void {
    const nuevo = (nombre ?? '').trim();
    if (!nuevo || nuevo === t.nombre) {
      return;
    }
    this.ejecutar(this.inventario.actualizarTipo(t.id, { nombre: nuevo }), `Tipo renombrado; los activos de tipo "${t.nombre}" se actualizaron.`);
  }

  protected cambiarEstadoTipo(t: TipoActivoCatalogo): void {
    this.ejecutar(
      this.inventario.actualizarTipo(t.id, { activo: !t.activo }),
      t.activo ? 'Tipo desactivado: ya no se ofrece en altas nuevas.' : 'Tipo reactivado.',
    );
  }

  // ------------------------------------------------------- Estados de activo

  protected crearEstado(): void {
    if (this.formEstado.invalid) {
      this.formEstado.markAllAsTouched();
      return;
    }
    const v = this.formEstado.getRawValue();
    this.ejecutar(
      this.inventario.crearEstado({ nombre: v.nombre.trim(), etiqueta: v.etiqueta.trim(), color: v.color }),
      'Estado creado.',
      () => this.formEstado.reset({ nombre: '', etiqueta: '', color: 'medium' }),
    );
  }

  protected editarEstado(
    e: EstadoActivoCatalogo,
    cambios: Partial<Pick<EstadoActivoCatalogo, 'etiqueta' | 'color' | 'orden'>>,
  ): void {
    const [campo, valor] = Object.entries(cambios)[0] ?? [];
    const limpio = typeof valor === 'string' ? valor.trim() : valor;
    if (!campo || limpio === '' || limpio === null || limpio === e[campo as keyof EstadoActivoCatalogo]) {
      return;
    }
    this.ejecutar(this.inventario.actualizarEstado(e.id, { [campo]: limpio }), 'Estado actualizado.');
  }

  protected cambiarVigenciaEstado(e: EstadoActivoCatalogo): void {
    this.ejecutar(
      this.inventario.actualizarEstado(e.id, { activo: !e.activo }),
      e.activo ? 'Estado desactivado: ya no se ofrece al registrar o editar activos.' : 'Estado reactivado.',
    );
  }

  // ------------------------------------------------------------------ común

  private ejecutar(operacion: Observable<unknown>, exito: string, despues?: () => void): void {
    this.mensaje.set(null);
    operacion.subscribe({
      next: () => {
        this.mensaje.set({ texto: exito, error: false });
        despues?.();
        this.cargar();
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible guardar el cambio.'), error: true }),
    });
  }

  private cargar(): void {
    this.catalogos.ubicaciones(this.esAdmin).subscribe((lista) => this.ubicaciones.set(lista));
    this.catalogos.sensores().subscribe((lista) => this.sensores.set(lista));
    this.inventario.tipos(this.esAdmin).subscribe((lista) => this.tipos.set(lista));
    this.inventario.recargarEstados();
  }
}
