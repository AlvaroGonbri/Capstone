import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
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
  IonIcon,
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
  IonText,
} from '@ionic/angular';
import { addIcons } from 'ionicons';
import { fingerPrintOutline } from 'ionicons/icons';
import { Observable } from 'rxjs';
import {
  DiaSemana,
  EventoAcceso,
  PermisoAcceso,
  PersonaAutorizada,
  PuntoAcceso,
  ResultadoAcceso,
  UbicacionCatalogo,
} from '../../core/models';
import { AccesosService } from '../../core/services/accesos.service';
import { AuthService } from '../../core/services/auth.service';
import { CatalogosService, nombreUbicacion } from '../../core/services/catalogos.service';
import { mensajeErrorApi } from '../../core/services/inventario.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { copiarTexto } from '../../shared/texto.util';

type Pestana = 'registro' | 'puntos' | 'permisos';

const DIAS: DiaSemana[] = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];
const NOMBRE_DIA: Record<DiaSemana, string> = { Lun: 'Lun', Mar: 'Mar', Mie: 'Mié', Jue: 'Jue', Vie: 'Vie', Sab: 'Sáb', Dom: 'Dom' };

/** Una fila del registro: un intento, o varias fallas seguidas e iguales del mismo lector agrupadas. */
interface FilaRegistro {
  evento: EventoAcceso;
  cantidad: number;
  /** Fecha del intento más antiguo del grupo (la lista viene de la más reciente a la más antigua). */
  desde: string;
  /** Cada cuánto se repitió, en segundos (solo en grupos). */
  cadaSegundos: number | null;
}

/**
 * Agrupa las fallas del lector que se repiten seguidas (mismo lector, mismo detalle e identificador):
 * un lector desconectado deja cientos de filas idénticas que ocultan los intentos reales.
 */
function agruparFallas(eventos: EventoAcceso[]): FilaRegistro[] {
  const filas: FilaRegistro[] = [];
  for (const e of eventos) {
    const anterior = filas[filas.length - 1];
    const repetida =
      anterior &&
      e.resultado === 'Error' &&
      anterior.evento.resultado === 'Error' &&
      anterior.evento.punto_acceso === e.punto_acceso &&
      anterior.evento.motivo === e.motivo &&
      anterior.evento.identificador_biometrico_externo === e.identificador_biometrico_externo;
    if (repetida) {
      anterior.cantidad += 1;
      anterior.desde = e.fecha_hora;
    } else {
      filas.push({ evento: e, cantidad: 1, desde: e.fecha_hora, cadaSegundos: null });
    }
  }
  for (const f of filas) {
    if (f.cantidad > 1) {
      const segundos = (new Date(f.evento.fecha_hora).getTime() - new Date(f.desde).getTime()) / 1000;
      f.cadaSegundos = Math.max(1, Math.round(segundos / (f.cantidad - 1)));
    }
  }
  return filas;
}

/** "cada 4 s" o "cada 2 min". */
function textoIntervalo(segundos: number): string {
  return segundos < 120 ? `cada ${segundos} s` : `cada ${Math.round(segundos / 60)} min`;
}

/** Cómo se muestra cada resultado (el valor guardado no cambia). "Error" es una falla del lector, no una advertencia. */
const ETIQUETA_RESULTADO: Record<ResultadoAcceso, string> = {
  Permitido: 'Autorizado',
  Denegado: 'Denegado',
  Error: 'Falla del lector',
};

@Component({
  selector: 'app-accesos',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    EncabezadoComponent,
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonIcon,
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
    IonText,
  ],
  templateUrl: './accesos.page.html',
  styleUrl: './accesos.page.scss',
})
export class AccesosPage {
  private readonly servicio = inject(AccesosService);
  private readonly catalogos = inject(CatalogosService);
  private readonly fb = inject(FormBuilder);

  /** Lectores y permisos los mantiene el Administrador; el personal externo, en su propia pantalla. */
  protected readonly esAdmin = inject(AuthService).puedeModificar('administrador', 'administradorprivilegiado');
  protected readonly pestana = signal<Pestana>('registro');
  protected readonly mensaje = signal<{ texto: string; error: boolean } | null>(null);
  protected readonly nombreUbicacion = nombreUbicacion;
  protected readonly dias = DIAS;
  protected readonly nombreDia = NOMBRE_DIA;
  protected readonly etiquetaResultado = (resultado: ResultadoAcceso) => ETIQUETA_RESULTADO[resultado] ?? resultado;

  // RF-ACC-03: registro y filtros del Auditor.
  protected readonly cargando = signal(true);
  protected readonly eventos = signal<EventoAcceso[]>([]);
  protected readonly filtros = this.fb.nonNullable.group({
    desde: [''],
    hasta: [''],
    resultado: ['' as ResultadoAcceso | ''],
    punto: [0],
    q: [''],
  });

  protected readonly personas = signal<PersonaAutorizada[]>([]);
  protected readonly puntos = signal<PuntoAcceso[]>([]);
  protected readonly permisos = signal<PermisoAcceso[]>([]);
  protected readonly ubicaciones = signal<UbicacionCatalogo[]>([]);
  /** Clave del agente recién creada o regenerada: se muestra una sola vez. */
  protected readonly claveNueva = signal<{ punto: string; id: number; clave: string } | null>(null);
  protected readonly claveCopiada = signal(false);

  /** Resumen de los intentos cargados (con los filtros actuales). */
  protected readonly resumen = computed(() => {
    const eventos = this.eventos();
    const contar = (resultado: ResultadoAcceso) => eventos.filter((e) => e.resultado === resultado).length;
    return { total: eventos.length, autorizados: contar('Permitido'), denegados: contar('Denegado'), fallas: contar('Error') };
  });
  protected readonly permisosActivos = computed(() => this.permisos().filter((p) => p.estado === 'Activo').length);
  protected readonly filas = computed(() => agruparFallas(this.eventos()));
  protected readonly textoIntervalo = textoIntervalo;

  protected readonly formPunto = this.fb.group({
    nombre: this.fb.nonNullable.control('', [Validators.required, Validators.maxLength(150)]),
    ubicacion: this.fb.control<number | null>(null, [Validators.required]),
  });
  protected readonly formPermiso = this.fb.group({
    persona: this.fb.control<number | null>(null, [Validators.required]),
    punto_acceso: this.fb.control<number | null>(null, [Validators.required]),
    vigencia_inicio: this.fb.nonNullable.control(new Date().toISOString().slice(0, 10), [Validators.required]),
    vigencia_fin: this.fb.nonNullable.control(''),
    dias: this.fb.nonNullable.control<DiaSemana[]>([]),
    hora_inicio: this.fb.nonNullable.control('08:00'),
    hora_fin: this.fb.nonNullable.control('18:00'),
  });

  constructor() {
    addIcons({ fingerPrintOutline });
    this.buscar();
    this.servicio.puntos().subscribe({ next: (lista) => this.puntos.set(lista), error: () => undefined });
    if (this.esAdmin) {
      this.cargarAdministracion();
      this.catalogos.ubicaciones().subscribe((lista) => this.ubicaciones.set(lista));
    }
  }

  protected cambiarPestana(valor: unknown): void {
    this.pestana.set(valor as Pestana);
    this.mensaje.set(null);
  }

  // ------------------------------------------------------------- registro

  protected buscar(): void {
    const f = this.filtros.getRawValue();
    this.cargando.set(true);
    this.servicio
      .eventos({ desde: f.desde, hasta: f.hasta, resultado: f.resultado || undefined, punto: f.punto || undefined, q: f.q.trim() })
      .subscribe({
        next: (lista) => {
          this.eventos.set(lista);
          this.cargando.set(false);
        },
        error: () => {
          this.eventos.set([]);
          this.cargando.set(false);
          this.mensaje.set({ texto: 'No fue posible cargar el registro de accesos.', error: true });
        },
      });
  }

  protected limpiarFiltros(): void {
    this.filtros.reset();
    this.buscar();
  }

  protected colorResultado(resultado: ResultadoAcceso): string {
    return resultado === 'Permitido' ? 'success' : resultado === 'Denegado' ? 'danger' : 'warning';
  }

  // --------------------------------------------------------------- puntos

  protected crearPunto(): void {
    if (this.formPunto.invalid) {
      this.formPunto.markAllAsTouched();
      return;
    }
    const v = this.formPunto.getRawValue();
    this.mensaje.set(null);
    this.servicio.crearPunto({ nombre: v.nombre.trim(), ubicacion: v.ubicacion! }).subscribe({
      next: (creado) => {
        this.claveNueva.set({ punto: creado.nombre, id: creado.id, clave: creado.clave_dispositivo });
        this.claveCopiada.set(false);
        this.mensaje.set({ texto: 'Lector registrado.', error: false });
        this.formPunto.reset();
        this.cargarAdministracion();
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible registrar el lector.'), error: true }),
    });
  }

  protected async copiarClave(clave: string): Promise<void> {
    const copiada = await copiarTexto(clave);
    this.claveCopiada.set(copiada);
    if (!copiada) {
      this.mensaje.set({ texto: 'El navegador no permitió copiar: selecciona la clave y cópiala a mano.', error: true });
    }
  }

  protected regenerarClave(p: PuntoAcceso): void {
    if (!confirm(`¿Generar una clave nueva para "${p.nombre}"? El agente dejará de funcionar hasta que la actualices.`)) {
      return;
    }
    this.servicio.regenerarClave(p.id).subscribe({
      next: ({ id, nombre, clave_dispositivo }) => {
        this.claveNueva.set({ punto: nombre, id, clave: clave_dispositivo });
        this.claveCopiada.set(false);
      },
      error: () => this.mensaje.set({ texto: 'No fue posible generar la clave.', error: true }),
    });
  }

  protected cambiarEstadoPunto(p: PuntoAcceso): void {
    const activo = p.estado === 'Activo';
    this.ejecutar(
      this.servicio.editarPunto(p.id, { estado: activo ? 'Inactivo' : 'Activo' }),
      activo ? 'Lector desactivado: SICMA rechazará sus envíos.' : 'Lector reactivado.',
    );
  }

  // ------------------------------------------------------------- permisos

  protected crearPermiso(): void {
    if (this.formPermiso.invalid) {
      this.formPermiso.markAllAsTouched();
      return;
    }
    const v = this.formPermiso.getRawValue();
    this.ejecutar(
      this.servicio.crearPermiso({
        persona: v.persona!,
        punto_acceso: v.punto_acceso!,
        vigencia_inicio: v.vigencia_inicio,
        vigencia_fin: v.vigencia_fin || null,
        // Sin días marcados: el permiso vale todo el día, todos los días.
        dias: v.dias.map((dia) => ({ dia_semana: dia, hora_inicio: v.hora_inicio, hora_fin: v.hora_fin })),
      }),
      'Permiso creado.',
      () => this.formPermiso.patchValue({ persona: null, dias: [] }),
    );
  }

  protected alternarDia(dia: DiaSemana, marcado: boolean): void {
    const actuales = this.formPermiso.controls.dias.value;
    this.formPermiso.controls.dias.setValue(marcado ? [...actuales, dia] : actuales.filter((d) => d !== dia));
  }

  protected revocar(p: PermisoAcceso): void {
    if (!confirm(`¿Revocar el permiso de ${p.persona_nombre} en ${p.punto_nombre}? Tiene efecto inmediato.`)) {
      return;
    }
    this.ejecutar(this.servicio.editarPermiso(p.id, { estado: 'Revocado' }), 'Permiso revocado.');
  }

  protected resumenHorario(p: PermisoAcceso): string {
    if (p.dias.length === 0) {
      return 'Todos los días, todo el día';
    }
    return p.dias.map((d) => `${d.dia_semana} ${d.hora_inicio.slice(0, 5)}–${d.hora_fin.slice(0, 5)}`).join(' · ');
  }

  // ---------------------------------------------------------------- común

  private ejecutar(operacion: Observable<unknown>, exito: string, despues?: () => void): void {
    this.mensaje.set(null);
    operacion.subscribe({
      next: () => {
        this.mensaje.set({ texto: exito, error: false });
        despues?.();
        this.cargarAdministracion();
      },
      error: (r: { error?: unknown }) =>
        this.mensaje.set({ texto: mensajeErrorApi(r.error, 'No fue posible guardar el cambio.'), error: true }),
    });
  }

  private cargarAdministracion(): void {
    this.servicio.personas().subscribe({ next: (lista) => this.personas.set(lista), error: () => undefined });
    this.servicio.puntos().subscribe({ next: (lista) => this.puntos.set(lista), error: () => undefined });
    this.servicio.permisos().subscribe({ next: (lista) => this.permisos.set(lista), error: () => undefined });
  }
}
