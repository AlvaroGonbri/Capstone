import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
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
  IonSkeletonText,
  IonText,
  IonTextarea,
} from '@ionic/angular';
import { Observable } from 'rxjs';
import { ActivoInventario, EstadoIntervencion, Intervencion, TecnicoAsignable } from '../../core/models';
import { AuthService } from '../../core/services/auth.service';
import {
  ESTADOS_CERRADOS,
  IntervencionesService,
  colorEstadoIntervencion,
  etiquetaEstadoIntervencion,
  tituloIntervencion,
} from '../../core/services/intervenciones.service';
import { InventarioService, mensajeErrorApi } from '../../core/services/inventario.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

type Filtro = 'abiertas' | 'Pendiente' | 'Aprobada' | 'EnEjecucion' | 'cerradas' | 'todas';

const DURACION_SUGERIDA_MS = 2 * 60 * 60 * 1000;

/** 'YYYY-MM-DDTHH:mm' en hora local, el formato de <input type="datetime-local">. */
function aEntradaLocal(iso: string | null): string {
  if (!iso) {
    return '';
  }
  const fecha = new Date(iso);
  const desfase = fecha.getTimezoneOffset() * 60_000;
  return new Date(fecha.getTime() - desfase).toISOString().slice(0, 16);
}

@Component({
  selector: 'app-intervenciones',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    EncabezadoComponent,
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
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
    IonSkeletonText,
    IonText,
    IonTextarea,
  ],
  templateUrl: './intervenciones.page.html',
  styleUrl: './intervenciones.page.scss',
})
export class IntervencionesPage {
  private readonly servicio = inject(IntervencionesService);
  private readonly inventario = inject(InventarioService);
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  /** RF-INT-05: asigna y cancela el Administrador. RF-INT-06: ejecuta el técnico asignado. */
  protected readonly esAdmin = this.auth.puedeModificar('administrador', 'administradorprivilegiado');
  private readonly usuarioId = this.auth.usuario()?.id ?? null;

  protected readonly cargando = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly mensaje = signal<{ texto: string; error: boolean } | null>(null);
  protected readonly intervenciones = signal<Intervencion[]>([]);
  protected readonly tecnicos = signal<TecnicoAsignable[]>([]);
  protected readonly activos = signal<ActivoInventario[]>([]);
  protected readonly filtro = signal<Filtro>('abiertas');
  protected readonly seleccionada = signal<number | null>(null);
  protected readonly enviando = signal(false);

  protected readonly etiquetaEstado = etiquetaEstadoIntervencion;
  protected readonly colorEstado = colorEstadoIntervencion;
  protected readonly titulo = tituloIntervencion;

  protected readonly filtradas = computed(() => {
    const f = this.filtro();
    return this.intervenciones().filter((i) => {
      const cerrada = ESTADOS_CERRADOS.includes(i.estado);
      if (f === 'todas') return true;
      if (f === 'abiertas') return !cerrada;
      if (f === 'cerradas') return cerrada;
      return i.estado === f;
    });
  });

  protected readonly formAsignar = this.fb.group({
    tecnico: this.fb.control<number | null>(null, [Validators.required]),
    fecha_inicio: this.fb.nonNullable.control('', [Validators.required]),
    fecha_termino: this.fb.nonNullable.control('', [Validators.required]),
    activos: this.fb.nonNullable.control<number[]>([]),
  });
  protected readonly formCierre = this.fb.nonNullable.group({
    observacion: ['', [Validators.required, Validators.maxLength(4000)]],
  });
  protected readonly formCancelar = this.fb.nonNullable.group({
    motivo: ['', [Validators.required, Validators.maxLength(4000)]],
  });

  constructor() {
    this.cargar();
    if (this.esAdmin) {
      this.cargarTecnicos();
      this.inventario.listar().subscribe({ next: (lista) => this.activos.set(lista), error: () => undefined });
    }
  }

  private cargarTecnicos(): void {
    this.servicio.tecnicos().subscribe({ next: (lista) => this.tecnicos.set(lista), error: () => undefined });
  }

  protected cambiarFiltro(valor: unknown): void {
    this.filtro.set(valor as Filtro);
  }

  protected alternar(i: Intervencion): void {
    if (this.seleccionada() === i.id) {
      this.seleccionada.set(null);
      return;
    }
    this.seleccionada.set(i.id);
    this.mensaje.set(null);
    // El formulario de Forms no pide término: se sugiere el inicio + 2 horas.
    const terminoSugerido = i.fecha_inicio
      ? new Date(new Date(i.fecha_inicio).getTime() + DURACION_SUGERIDA_MS).toISOString()
      : null;
    this.formAsignar.reset({
      tecnico: i.responsable,
      fecha_inicio: aEntradaLocal(i.fecha_inicio),
      fecha_termino: aEntradaLocal(i.fecha_termino ?? terminoSugerido),
      activos: i.activos.map((a) => a.id),
    });
    if (this.esAdmin && i.estado === 'Aprobada') {
      this.cargarTecnicos(); // refleja correos o roles cambiados en Usuarios
    }
    this.formCierre.reset();
    this.formCancelar.reset();
  }

  /** El técnico asignado o un Administrador registran la ejecución. */
  protected puedeEjecutar(i: Intervencion): boolean {
    if (this.auth.soloConsulta) {
      return false;
    }
    return this.esAdmin || (i.responsable !== null && i.responsable === this.usuarioId);
  }

  protected puedeCancelar(estado: EstadoIntervencion): boolean {
    return this.esAdmin && (estado === 'Pendiente' || estado === 'Aprobada');
  }

  protected asignar(i: Intervencion): void {
    if (this.formAsignar.invalid) {
      this.formAsignar.markAllAsTouched();
      this.mensaje.set({ texto: 'Elige el técnico y el horario de inicio y término.', error: true });
      return;
    }
    const v = this.formAsignar.getRawValue();
    this.ejecutar(
      this.servicio.asignar(i.id, {
        tecnico: v.tecnico!,
        fecha_inicio: new Date(v.fecha_inicio).toISOString(),
        fecha_termino: new Date(v.fecha_termino).toISOString(),
        activos: v.activos,
      }),
      'Técnico asignado. SICMA pidió al flujo agendarla en el calendario de Outlook.',
    );
  }

  protected iniciar(i: Intervencion): void {
    this.ejecutar(this.servicio.iniciar(i.id), 'Intervención iniciada.');
  }

  protected cerrar(i: Intervencion, exitosa: boolean): void {
    if (this.formCierre.invalid) {
      this.formCierre.markAllAsTouched();
      this.mensaje.set({ texto: 'Describe qué se hizo antes de cerrar.', error: true });
      return;
    }
    this.ejecutar(
      this.servicio.cerrar(i.id, exitosa, this.formCierre.getRawValue().observacion.trim()),
      exitosa ? 'Intervención cerrada como ejecutada.' : 'Intervención cerrada como fallida.',
    );
  }

  protected cancelar(i: Intervencion): void {
    if (this.formCancelar.invalid) {
      this.formCancelar.markAllAsTouched();
      this.mensaje.set({ texto: 'Indica el motivo de la cancelación.', error: true });
      return;
    }
    this.ejecutar(this.servicio.cancelar(i.id, this.formCancelar.getRawValue().motivo.trim()), 'Intervención cancelada.');
  }

  private ejecutar(operacion: Observable<Intervencion>, exito: string): void {
    this.enviando.set(true);
    this.mensaje.set(null);
    operacion.subscribe({
      next: (actualizada) => {
        this.intervenciones.update((lista) => lista.map((i) => (i.id === actualizada.id ? actualizada : i)));
        this.mensaje.set({ texto: exito, error: false });
        this.enviando.set(false);
      },
      error: (r: { error?: unknown }) => {
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible guardar el cambio.'), error: true });
        this.enviando.set(false);
      },
    });
  }

  private cargar(): void {
    this.servicio.listar().subscribe({
      next: (lista) => {
        this.intervenciones.set(lista);
        this.error.set(null);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No fue posible cargar las intervenciones.');
        this.cargando.set(false);
      },
    });
  }
}
