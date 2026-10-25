import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, signal } from '@angular/core';
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
  IonSearchbar,
  IonSelect,
  IonSelectOption,
  IonSkeletonText,
  IonSpinner,
  IonText,
} from '@ionic/angular';
import { Observable } from 'rxjs';
import { CambioHabilitacion, PersonaAutorizada, PuntoAcceso, SolicitudEnrolamiento } from '../../core/models';
import { AccesosService } from '../../core/services/accesos.service';
import { AuthService } from '../../core/services/auth.service';
import { mensajeErrorApi } from '../../core/services/inventario.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

const ENROLAMIENTO_ABIERTO = ['Pendiente', 'EnCurso'];
const CONSULTA_ENROLAMIENTO_MS = 1000;

/**
 * Personal externo (RF-ACC): el Departamento de contratistas registra a cada persona con su RUT,
 * enrola su huella en el lector y la habilita o deshabilita para trabajar en el datacenter.
 */
@Component({
  selector: 'app-personal',
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
    IonSearchbar,
    IonSelect,
    IonSelectOption,
    IonSkeletonText,
    IonSpinner,
    IonText,
  ],
  templateUrl: './personal.page.html',
  styleUrl: './personal.page.scss',
})
export class PersonalPage {
  private readonly servicio = inject(AccesosService);
  private readonly fb = inject(FormBuilder);

  /** Registran, enrolan y habilitan: Departamento de contratistas y Administrador. El resto consulta. */
  protected readonly puedeEditar = inject(AuthService).puedeModificar('contratistas', 'administrador', 'administradorprivilegiado');

  protected readonly cargando = signal(true);
  protected readonly personas = signal<PersonaAutorizada[]>([]);
  protected readonly puntos = signal<PuntoAcceso[]>([]);
  protected readonly busqueda = signal('');
  protected readonly seleccionada = signal<PersonaAutorizada | null>(null);
  protected readonly historial = signal<CambioHabilitacion[]>([]);
  protected readonly mensaje = signal<{ texto: string; error: boolean } | null>(null);
  /** Solicitud en curso de la persona abierta: se consulta cada 2 s hasta que el agente responde. */
  protected readonly enrolamiento = signal<SolicitudEnrolamiento | null>(null);
  private temporizador: ReturnType<typeof setInterval> | null = null;

  protected readonly formAlta = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(150)]],
    rut: ['', [Validators.required, Validators.maxLength(12)]],
    empresa: ['', [Validators.required, Validators.maxLength(150)]],
  });
  protected readonly formEdicion = this.fb.nonNullable.group({
    nombre: ['', [Validators.required, Validators.maxLength(150)]],
    rut: ['', [Validators.required, Validators.maxLength(12)]],
    empresa: ['', [Validators.required, Validators.maxLength(150)]],
  });
  protected readonly formHabilitacion = this.fb.nonNullable.group({ motivo: ['', [Validators.maxLength(255)]] });
  protected readonly puntoEnrolamiento = this.fb.control<number | null>(null);

  constructor() {
    this.buscar();
    this.servicio.puntos().subscribe({
      next: (lista) => {
        const activos = lista.filter((p) => p.estado === 'Activo');
        this.puntos.set(activos);
        if (activos.length === 1) {
          this.puntoEnrolamiento.setValue(activos[0].id);
        }
      },
      error: () => undefined,
    });
    inject(DestroyRef).onDestroy(() => this.detenerConsulta());
  }

  protected buscar(texto = this.busqueda()): void {
    this.busqueda.set(texto);
    this.servicio.personas(texto.trim()).subscribe({
      next: (lista) => {
        this.personas.set(lista);
        this.cargando.set(false);
      },
      error: () => {
        this.cargando.set(false);
        this.mensaje.set({ texto: 'No fue posible cargar el personal externo.', error: true });
      },
    });
  }

  protected abrir(p: PersonaAutorizada): void {
    if (this.seleccionada()?.id === p.id) {
      this.cerrar();
      return;
    }
    this.detenerConsulta();
    this.seleccionada.set(p);
    this.mensaje.set(null);
    this.formEdicion.reset({ nombre: p.nombre, rut: p.rut ?? '', empresa: p.empresa ?? '' });
    this.formHabilitacion.reset();
    this.enrolamiento.set(p.enrolamiento);
    if (p.enrolamiento && ENROLAMIENTO_ABIERTO.includes(p.enrolamiento.estado)) {
      this.consultarEnrolamiento(p.enrolamiento.id);
    }
    this.servicio.historialHabilitacion(p.id).subscribe({ next: (h) => this.historial.set(h), error: () => this.historial.set([]) });
  }

  protected cerrar(): void {
    this.detenerConsulta();
    this.seleccionada.set(null);
  }

  // ----------------------------------------------------------------- ficha

  protected registrar(): void {
    if (this.formAlta.invalid) {
      this.formAlta.markAllAsTouched();
      this.mensaje.set({ texto: 'Completa nombre, RUT y empresa.', error: true });
      return;
    }
    const v = this.formAlta.getRawValue();
    this.ejecutar(
      this.servicio.crearPersona({ nombre: v.nombre.trim(), rut: v.rut.trim(), empresa: v.empresa.trim() }),
      'Persona registrada. Ahora enrola su huella con la persona frente al lector.',
      (persona) => {
        this.formAlta.reset();
        this.abrir(persona);
      },
    );
  }

  protected guardarDatos(p: PersonaAutorizada): void {
    if (this.formEdicion.invalid) {
      this.formEdicion.markAllAsTouched();
      return;
    }
    const v = this.formEdicion.getRawValue();
    this.ejecutar(
      this.servicio.editarPersona(p.id, { nombre: v.nombre.trim(), rut: v.rut.trim(), empresa: v.empresa.trim() }),
      'Datos actualizados.',
    );
  }

  protected eliminar(p: PersonaAutorizada): void {
    const confirmado = confirm(
      `¿Eliminar a ${p.nombre} (RUT ${p.rut || '—'})?\n\n` +
        '• Se borra su ficha, sus permisos y su historial de habilitación.\n' +
        '• Los lectores borran su huella.\n' +
        '• Sus intentos de acceso se conservan en el registro con el identificador ' + p.identificador_biometrico_externo + '.\n\n' +
        'No se puede deshacer.',
    );
    if (!confirmado) {
      return;
    }
    this.mensaje.set(null);
    this.servicio.eliminarPersona(p.id).subscribe({
      next: ({ lectores_notificados }) => {
        this.cerrar();
        this.personas.update((lista) => lista.filter((x) => x.id !== p.id));
        this.mensaje.set({
          texto: `${p.nombre} fue eliminado. ` + (lectores_notificados
            ? 'El lector borrará su huella en los próximos segundos.'
            : 'No había lectores con su huella.'),
          error: false,
        });
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible eliminar a la persona.'), error: true }),
    });
  }

  // ----------------------------------------------------------- habilitación

  protected cambiarHabilitacion(p: PersonaAutorizada): void {
    const habilitar = p.estado !== 'Activo';
    const motivo = this.formHabilitacion.getRawValue().motivo.trim();
    if (!habilitar && !motivo) {
      this.mensaje.set({ texto: 'Indica el motivo para deshabilitar (p. ej. cotizaciones vencidas).', error: true });
      return;
    }
    this.ejecutar(
      this.servicio.cambiarHabilitacion(p.id, habilitar, motivo),
      habilitar ? 'Persona habilitada para trabajar en el datacenter.' : 'Persona deshabilitada: el lector le negará el acceso.',
      (actualizada) => {
        this.formHabilitacion.reset();
        this.servicio.historialHabilitacion(actualizada.id).subscribe({ next: (h) => this.historial.set(h), error: () => undefined });
      },
    );
  }

  // ----------------------------------------------------------- enrolamiento

  protected enrolar(p: PersonaAutorizada): void {
    const punto = this.puntoEnrolamiento.value ?? undefined;
    if (this.puntos().length > 1 && !punto) {
      this.mensaje.set({ texto: 'Elige en qué lector se enrolará la huella.', error: true });
      return;
    }
    this.mensaje.set(null);
    this.servicio.enrolar(p.id, punto).subscribe({
      next: (solicitud) => {
        this.enrolamiento.set(solicitud);
        this.consultarEnrolamiento(solicitud.id);
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible solicitar el enrolamiento.'), error: true }),
    });
  }

  protected cancelarEnrolamiento(solicitud: SolicitudEnrolamiento): void {
    this.servicio.cancelarEnrolamiento(solicitud.id).subscribe({
      next: (s) => {
        this.detenerConsulta();
        this.enrolamiento.set(s);
      },
      error: () => undefined,
    });
  }

  protected enCurso(solicitud: SolicitudEnrolamiento | null): boolean {
    return !!solicitud && ENROLAMIENTO_ABIERTO.includes(solicitud.estado);
  }

  /** Muestras ya tomadas (para la barra de avance): la actual cuenta recién cuando el agente la registra. */
  protected muestrasListas(e: SolicitudEnrolamiento): number {
    const registrada = e.indicacion.startsWith('Muestra registrada');
    return Math.max(0, e.muestra - (registrada ? 0 : 1));
  }

  protected pasos(e: SolicitudEnrolamiento): number[] {
    return Array.from({ length: e.total_muestras || 3 }, (_, i) => i + 1);
  }

  private consultarEnrolamiento(id: number): void {
    this.detenerConsulta();
    this.temporizador = setInterval(() => {
      this.servicio.enrolamiento(id).subscribe({
        next: (s) => {
          this.enrolamiento.set(s);
          if (!ENROLAMIENTO_ABIERTO.includes(s.estado)) {
            this.detenerConsulta();
            this.refrescarSeleccionada();
          }
        },
        error: () => this.detenerConsulta(),
      });
    }, CONSULTA_ENROLAMIENTO_MS);
  }

  private detenerConsulta(): void {
    if (this.temporizador) {
      clearInterval(this.temporizador);
      this.temporizador = null;
    }
  }

  // ------------------------------------------------------------------ común

  private refrescarSeleccionada(): void {
    const actual = this.seleccionada();
    if (!actual) {
      return;
    }
    this.servicio.persona(actual.id).subscribe({
      next: (p) => {
        this.seleccionada.set(p);
        this.personas.update((lista) => lista.map((x) => (x.id === p.id ? p : x)));
      },
      error: () => undefined,
    });
  }

  private ejecutar(operacion: Observable<PersonaAutorizada>, exito: string, despues?: (p: PersonaAutorizada) => void): void {
    this.mensaje.set(null);
    operacion.subscribe({
      next: (persona) => {
        this.mensaje.set({ texto: exito, error: false });
        this.personas.update((lista) =>
          lista.some((x) => x.id === persona.id) ? lista.map((x) => (x.id === persona.id ? persona : x)) : [persona, ...lista],
        );
        if (this.seleccionada()?.id === persona.id) {
          this.seleccionada.set(persona);
        }
        despues?.(persona);
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible guardar el cambio.'), error: true }),
    });
  }
}
