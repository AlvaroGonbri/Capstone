import { Component, computed, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonInput,
  IonItem,
  IonList,
  IonNote,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonText,
  IonTextarea,
  IonTitle,
  IonToolbar,
} from '@ionic/angular';
import { forkJoin } from 'rxjs';
import {
  ActivoInventario,
  Criticidad,
  EstadoInventario,
  TipoActivoCatalogo,
  UbicacionCatalogo,
  UsuarioResumen,
} from '../../core/models';
import { CatalogosService, nombreUbicacion } from '../../core/services/catalogos.service';
import {
  CRITICIDADES,
  DatosActivo,
  ESTADO_INICIAL,
  ESTADO_RETIRADO,
  InventarioService,
  mensajeErrorApi,
} from '../../core/services/inventario.service';

@Component({
  selector: 'app-activo-form',
  imports: [
    ReactiveFormsModule,
    IonBackButton,
    IonButton,
    IonButtons,
    IonContent,
    IonHeader,
    IonInput,
    IonItem,
    IonList,
    IonNote,
    IonSelect,
    IonSelectOption,
    IonSpinner,
    IonText,
    IonTextarea,
    IonTitle,
    IonToolbar,
  ],
  templateUrl: './activo-form.page.html',
})
export class ActivoFormPage {
  /** Presente al editar (/activos/:id/editar); ausente al registrar (/activos/nuevo). */
  readonly id = input<string>();

  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  private readonly inventario = inject(InventarioService);
  private readonly catalogos = inject(CatalogosService);

  protected readonly cargando = signal(true);
  protected readonly guardando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly original = signal<ActivoInventario | null>(null);
  private readonly tiposCatalogo = signal<TipoActivoCatalogo[]>([]);
  private readonly ubicacionesActivas = signal<UbicacionCatalogo[]>([]);
  protected readonly usuarios = signal<UsuarioResumen[]>([]);

  /** Al editar se conserva el estado actual aunque luego se haya desactivado; en el alta no se ofrece la baja. */
  protected readonly estados = computed(() =>
    this.inventario
      .estadosSeleccionables(this.original()?.estado)
      .filter((e) => this.editando() || e.nombre !== ESTADO_RETIRADO),
  );
  protected readonly criticidades = CRITICIDADES;
  protected readonly nombreUbicacion = nombreUbicacion;

  /** Al editar se conserva el tipo actual aunque luego se haya desactivado en el catálogo. */
  protected readonly tipos = computed(() => {
    const nombres = this.tiposCatalogo().map((t) => t.nombre);
    const actual = this.original()?.tipo;
    return actual && !nombres.includes(actual) ? [...nombres, actual] : nombres;
  });

  protected readonly ubicaciones = computed(() => {
    const lista = this.ubicacionesActivas().map((u) => ({ id: u.id, nombre: nombreUbicacion(u) }));
    const actual = this.original();
    return actual && !lista.some((u) => u.id === actual.ubicacion)
      ? [...lista, { id: actual.ubicacion, nombre: `${actual.ubicacion_nombre} (desactivada)` }]
      : lista;
  });

  protected readonly formulario = this.fb.group({
    codigo: this.fb.nonNullable.control('', [Validators.required, Validators.maxLength(50)]),
    nombre: this.fb.nonNullable.control('', [Validators.required, Validators.maxLength(200)]),
    tipo: this.fb.control<string | null>(null),
    marca: this.fb.control<string | null>(null, [Validators.maxLength(100)]),
    modelo: this.fb.control<string | null>(null, [Validators.maxLength(100)]),
    numero_serie: this.fb.nonNullable.control('', [Validators.required, Validators.maxLength(150)]),
    estado: this.fb.nonNullable.control<EstadoInventario>(ESTADO_INICIAL),
    criticidad: this.fb.nonNullable.control<Criticidad>('Media'),
    ubicacion: this.fb.control<number | null>(null, [Validators.required]),
    responsable: this.fb.control<number | null>(null),
    observaciones: this.fb.control<string | null>(null),
  });

  constructor() {
    queueMicrotask(() => this.cargar());
  }

  protected editando(): boolean {
    return !!this.id();
  }

  protected guardar(): void {
    if (this.formulario.invalid || this.guardando()) {
      this.formulario.markAllAsTouched();
      this.error.set('Revisa los campos obligatorios: código, nombre, número de serie y ubicación.');
      return;
    }
    const valores = this.formulario.getRawValue();
    const datos: DatosActivo = {
      ...valores,
      codigo: valores.codigo.trim(),
      numero_serie: valores.numero_serie.trim(),
      tipo: valores.tipo || null,
      marca: valores.marca?.trim() || null,
      modelo: valores.modelo?.trim() || null,
      observaciones: valores.observaciones?.trim() || null,
      ubicacion: valores.ubicacion!,
    };

    this.guardando.set(true);
    this.error.set(null);
    const id = this.id();
    const operacion = id ? this.inventario.actualizar(Number(id), datos) : this.inventario.crear(datos);
    operacion.subscribe({
      next: (activo) => void this.router.navigate(['/activos', activo.id], { replaceUrl: true }),
      error: (respuesta: { error?: unknown }) => {
        this.guardando.set(false);
        this.error.set(mensajeErrorApi(respuesta.error, 'No fue posible guardar el activo.'));
      },
    });
  }

  private cargar(): void {
    forkJoin({
      tipos: this.inventario.tipos(),
      ubicaciones: this.catalogos.ubicaciones(),
      usuarios: this.inventario.responsablesPosibles(),
    }).subscribe({
      next: ({ tipos, ubicaciones, usuarios }) => {
        this.tiposCatalogo.set(tipos);
        this.ubicacionesActivas.set(ubicaciones);
        this.usuarios.set(usuarios);
        const id = this.id();
        if (id) {
          this.inventario.obtener(Number(id)).subscribe({
            next: (activo) => {
              this.original.set(activo);
              this.formulario.reset(activo);
              this.formulario.controls.codigo.disable(); // el código vincula el activo con Zabbix
              this.cargando.set(false);
            },
            error: () => {
              this.error.set('No se encontró el activo.');
              this.cargando.set(false);
            },
          });
        } else {
          // Desde "Registrar" de un equipo de Zabbix llegan su código y nombre.
          const params = this.ruta.snapshot.queryParamMap;
          const desdeZabbix = params.has('codigo');
          this.formulario.patchValue({
            codigo: params.get('codigo') ?? '',
            nombre: params.get('nombre') ?? '',
            tipo: desdeZabbix && tipos.some((t) => t.nombre === 'Servidor') ? 'Servidor' : null,
            ubicacion: ubicaciones.length === 1 ? ubicaciones[0].id : null,
          });
          this.cargando.set(false);
        }
      },
      error: () => {
        this.error.set('No fue posible cargar los catálogos.');
        this.cargando.set(false);
      },
    });
  }
}
