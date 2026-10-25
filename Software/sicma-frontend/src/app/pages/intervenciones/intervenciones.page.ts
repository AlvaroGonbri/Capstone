import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
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
  IonSearchbar,
  IonSegment,
  IonSegmentButton,
  IonSelect,
  IonSelectOption,
  IonSkeletonText,
  IonSpinner,
  IonText,
  IonTextarea,
} from '@ionic/angular';
import { Observable } from 'rxjs';
import {
  ActivoInventario,
  EstadoIntervencion,
  Intervencion,
  PersonaAutorizada,
  PersonalIntervencion,
  SolicitudVerificacion,
  TecnicoAsignable,
} from '../../core/models';
import { AccesosService } from '../../core/services/accesos.service';
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
    IonSearchbar,
    IonSegment,
    IonSegmentButton,
    IonSelect,
    IonSelectOption,
    IonSkeletonText,
    IonSpinner,
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
  private readonly accesos = inject(AccesosService);

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
  /** Personal externo elegido para la intervención abierta (se guarda al asignar o con "Guardar personal"). */
  protected readonly personalElegido = signal<PersonalIntervencion[]>([]);
  protected readonly resultadosPersonal = signal<PersonaAutorizada[]>([]);
  protected readonly busquedaPersonal = signal('');
  /** Verificación de identidad en curso (persona → solicitud); se consulta cada segundo. */
  protected readonly verificando = signal<{ personaId: number; solicitud: SolicitudVerificacion } | null>(null);
  private temporizadorVerificacion: ReturnType<typeof setInterval> | null = null;

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
    inject(DestroyRef).onDestroy(() => this.detenerVerificacion());
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
    this.personalElegido.set([...i.personal_externo]);
    this.busquedaPersonal.set('');
    this.resultadosPersonal.set([]);
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

  /** Cancelan el Administrador y la Jefatura (que aprueba las intervenciones). */
  private readonly esJefatura = this.auth.puedeModificar('jefatura');

  protected puedeCancelar(estado: EstadoIntervencion): boolean {
    return (this.esAdmin || this.esJefatura) && (estado === 'Pendiente' || estado === 'Aprobada');
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
        personal_externo: this.personalElegido().map((p) => p.id),
      }),
      'Técnico asignado. SICMA pidió al flujo agendarla en el calendario de Outlook.',
    );
  }

  // ------------------------------------------------------- personal externo

  protected buscarPersonal(texto: string): void {
    this.busquedaPersonal.set(texto);
    if (texto.trim().length < 2) {
      this.resultadosPersonal.set([]);
      return;
    }
    this.accesos.personas(texto.trim()).subscribe({
      next: (lista) => this.resultadosPersonal.set(lista.slice(0, 8)),
      error: () => this.resultadosPersonal.set([]),
    });
  }

  /** Solo se puede elegir a quien está habilitado y tiene huella; si no, se dice por qué. */
  protected impedimento(p: PersonaAutorizada): string | null {
    if (p.estado !== 'Activo') return 'Deshabilitada';
    if (!p.huella_registrada_en) return 'Sin huella registrada';
    if (this.personalElegido().some((x) => x.id === p.id)) return 'Ya agregada';
    return null;
  }

  protected agregarPersonal(p: PersonaAutorizada): void {
    if (this.impedimento(p)) {
      return;
    }
    this.personalElegido.update((lista) => [
      ...lista,
      { id: p.id, nombre: p.nombre, rut: p.rut, empresa: p.empresa, identificador: p.identificador_biometrico_externo, habilitada: true, huella_registrada: true, verificada_en: null, verificacion: null },
    ]);
  }

  protected quitarPersonal(id: number): void {
    this.personalElegido.update((lista) => lista.filter((p) => p.id !== id));
  }

  protected guardarPersonal(i: Intervencion): void {
    this.ejecutar(
      this.servicio.guardarPersonal(i.id, this.personalElegido().map((p) => p.id)),
      'Personal externo actualizado.',
    );
  }

  // --------------------------------------------- verificación de identidad

  /** El técnico asignado (o un Administrador) verifica al personal externo antes de iniciar. */
  protected puedeVerificar(i: Intervencion): boolean {
    return i.estado === 'Aprobada' && !!i.responsable && this.puedeEjecutar(i) && i.personal_externo.length > 0;
  }

  protected readonly nombrePersona = (p: PersonalIntervencion) => p.nombre;

  protected pendientesDeVerificar(i: Intervencion): PersonalIntervencion[] {
    return i.personal_externo.filter((p) => !p.verificada_en || !p.habilitada);
  }

  protected verificar(i: Intervencion, p: PersonalIntervencion): void {
    this.mensaje.set(null);
    this.servicio.verificarPersona(i.id, p.id).subscribe({
      next: (solicitud) => {
        this.verificando.set({ personaId: p.id, solicitud });
        this.consultarVerificacion(i.id, p.id, solicitud.id);
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible pedir la verificación.'), error: true }),
    });
  }

  private consultarVerificacion(intervencionId: number, personaId: number, solicitudId: number): void {
    this.detenerVerificacion();
    this.temporizadorVerificacion = setInterval(() => {
      this.servicio.verificacion(solicitudId).subscribe({
        next: (s) => {
          this.verificando.set({ personaId, solicitud: s });
          if (s.estado !== 'Pendiente' && s.estado !== 'EnCurso') {
            this.detenerVerificacion();
            this.recargarIntervencion(intervencionId);
            this.mensaje.set({
              texto: s.estado === 'Completada' ? 'Identidad verificada.' : `No verificada: ${s.mensaje}`,
              error: s.estado !== 'Completada',
            });
          }
        },
        error: () => this.detenerVerificacion(),
      });
    }, 1000);
  }

  private detenerVerificacion(): void {
    if (this.temporizadorVerificacion) {
      clearInterval(this.temporizadorVerificacion);
      this.temporizadorVerificacion = null;
    }
  }

  private recargarIntervencion(id: number): void {
    this.servicio.listar().subscribe({
      next: (lista) => this.intervenciones.set(lista),
      error: () => undefined,
    });
    this.verificando.update((v) => (v && v.solicitud.intervencion_id === id ? null : v));
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
