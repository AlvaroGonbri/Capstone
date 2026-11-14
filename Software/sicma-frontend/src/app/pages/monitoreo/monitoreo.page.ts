import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonInput,
  IonNote,
  IonRefresher,
  IonRefresherContent,
  IonSkeletonText,
  IonSpinner,
} from '@ionic/angular';
import { Observable, forkJoin } from 'rxjs';
import { Alerta, EstadoSensor, UmbralZona, Umbrales, VersionUmbral } from '../../core/models';
import { AlertasService } from '../../core/services/alertas.service';
import { AuthService } from '../../core/services/auth.service';
import { MonitoreoService, VariableAmbiental } from '../../core/services/monitoreo.service';
import { posicionesBarra, rangoTexto, respectoDelRango } from '../../core/services/umbrales.util';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { GraficoAmbientalComponent, SensorGrafico } from '../../shared/grafico-ambiental.component';
import { HacePipe } from '../../shared/hace.pipe';
import { ColorNivelPipe } from '../../shared/nivel.pipe';
import { environment } from '../../../environments/environment';

type CampoUmbral = keyof Umbrales;

/** Validación básica en pantalla; el backend valida de nuevo al guardar. */
const CORREO_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const VARIABLES: Array<{ variable: VariableAmbiental; minimo: CampoUmbral; maximo: CampoUmbral }> = [
  { variable: 'Temperatura', minimo: 'temperaturaMinima', maximo: 'temperaturaMaxima' },
  { variable: 'Humedad', minimo: 'humedadMinima', maximo: 'humedadMaxima' },
];

@Component({
  selector: 'app-monitoreo',
  imports: [
    DatePipe,
    EncabezadoComponent,
    ColorNivelPipe,
    GraficoAmbientalComponent,
    HacePipe,
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonInput,
    IonNote,
    IonRefresher,
    IonRefresherContent,
    IonSkeletonText,
    IonSpinner,
  ],
  templateUrl: './monitoreo.page.html',
  styleUrl: './monitoreo.page.scss',
})
export class MonitoreoPage {
  private readonly servicio = inject(MonitoreoService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly cargando = signal(true);
  protected readonly sensores = signal<EstadoSensor[]>([]);
  /** Alertas ambientales abiertas (RF-AMB-04). */
  protected readonly alertas = signal<Alerta[]>([]);
  protected readonly actualizadoEn = signal<Date>(new Date());
  protected readonly rango = rangoTexto;
  protected readonly barra = posicionesBarra;
  protected readonly respecto = respectoDelRango;

  /** Solo cuentan los sensores que reportan: la lectura de uno sin datos ya no es actual. */
  protected readonly enAlerta = computed(() =>
    this.sensores().filter((s) => s.conexion === 'En línea' && s.nivel !== 'normal').length,
  );
  protected readonly sinDatos = computed(() => this.sensores().filter((s) => s.conexion === 'Sin datos').length);

  /** Sensores para el historial de temperatura y humedad: primero los que están reportando. */
  protected readonly sensoresGrafico = computed<SensorGrafico[]>(() =>
    [...this.sensores()]
      .sort((a, b) => Number(b.conexion === 'En línea') - Number(a.conexion === 'En línea'))
      .map((s) => ({ id: s.id, codigo: s.sensorId, ubicacion: s.ubicacion })),
  );

  /** RF-AMB-03: solo el Administrador define los umbrales (matriz de permisos). */
  protected readonly puedeEditarUmbrales = computed(() => {
    return this.auth.puedeModificar('administrador', 'administradorprivilegiado');
  });
  /** Copia editable de los umbrales de cada zona. */
  protected readonly zonas = signal<UmbralZona[]>([]);
  protected readonly guardandoZona = signal<number | null>(null);
  protected readonly mensajeZona = signal<{ ubicacionId: number; texto: string; error: boolean } | null>(null);
  private originales = new Map<number, UmbralZona>();
  /** Correo que se está escribiendo en cada zona, antes de agregarlo a la lista. */
  protected readonly borradorCorreo = signal<Partial<Record<number, string>>>({});
  /** Historial abierto (una zona a la vez); versiones null mientras carga. */
  protected readonly historial = signal<{ ubicacionId: number; versiones: VersionUmbral[] | null } | null>(null);

  constructor() {
    this.cargar();
    this.cargarZonas();

    const temporizador = setInterval(() => this.cargar(), environment.refrescoMonitoreoMs);
    this.destroyRef.onDestroy(() => clearInterval(temporizador));
  }

  protected cargar(evento?: CustomEvent): void {
    this.servicio.estadoSensores().subscribe((lista) => {
      this.sensores.set(lista);
      this.actualizadoEn.set(new Date());
      this.cargando.set(false);
      (evento?.target as HTMLIonRefresherElement | undefined)?.complete();
    });
    this.servicio.alertasAbiertas().subscribe({
      next: (alertas) => this.alertas.set(alertas),
      error: () => undefined, // la lista de alertas no debe impedir ver las lecturas
    });
  }

  protected fueraDeRango(sensor: EstadoSensor, variable: 'temperatura' | 'humedad'): boolean {
    return sensor.motivos.some((motivo) => motivo.startsWith(variable));
  }

  protected editarValor(zona: UmbralZona, campo: CampoUmbral, valor: string | number | null | undefined): void {
    const numero = valor === '' || valor === null || valor === undefined ? null : Number(valor);
    if (numero !== null && !Number.isFinite(numero)) {
      return;
    }
    this.zonas.update((lista) =>
      lista.map((item) => (item.ubicacionId === zona.ubicacionId ? { ...item, [campo]: numero } : item)),
    );
  }

  // ------------------------------------------- responsables de alerta ("Notificar a")

  protected escribirCorreo(zona: UmbralZona, texto: string | null | undefined): void {
    this.borradorCorreo.update((b) => ({ ...b, [zona.ubicacionId]: texto ?? '' }));
  }

  /** Agrega el correo escrito a la lista de la zona (se guarda con "Guardar"). Devuelve false si no es válido. */
  protected agregarCorreo(zona: UmbralZona): boolean {
    const correo = (this.borradorCorreo()[zona.ubicacionId] ?? '').trim().toLowerCase();
    if (!correo) {
      return true;
    }
    if (!CORREO_VALIDO.test(correo)) {
      this.avisar(zona, `«${correo}» no es un correo válido.`, true);
      return false;
    }
    if (!zona.correos.includes(correo)) {
      this.zonas.update((lista) =>
        lista.map((item) => (item.ubicacionId === zona.ubicacionId ? { ...item, correos: [...item.correos, correo] } : item)),
      );
    }
    this.borradorCorreo.update((b) => ({ ...b, [zona.ubicacionId]: '' }));
    this.mensajeZona.set(null);
    return true;
  }

  protected quitarCorreo(zona: UmbralZona, correo: string): void {
    this.zonas.update((lista) =>
      lista.map((item) =>
        item.ubicacionId === zona.ubicacionId ? { ...item, correos: item.correos.filter((c) => c !== correo) } : item,
      ),
    );
  }

  // ------------------------------------------------------ historial de umbrales

  protected verHistorial(zona: UmbralZona): void {
    if (this.historial()?.ubicacionId === zona.ubicacionId) {
      this.historial.set(null);
      return;
    }
    this.historial.set({ ubicacionId: zona.ubicacionId, versiones: null });
    this.servicio.historialUmbrales(zona.ubicacionId).subscribe({
      next: (versiones) =>
        this.historial.update((h) => (h?.ubicacionId === zona.ubicacionId ? { ...h, versiones } : h)),
      error: () => {
        this.historial.set(null);
        this.avisar(zona, 'No fue posible cargar el historial de cambios.', true);
      },
    });
  }

  /** La primera versión de cada variable en el historial (ordenado de la más reciente) es la vigente. */
  protected esVigente(versiones: VersionUmbral[], v: VersionUmbral): boolean {
    return versiones.find((x) => x.variable === v.variable) === v;
  }

  /**
   * Un solo Guardar por zona: los umbrales que cambiaron y la lista de responsables, si cambió.
   * Si se escribió un correo sin presionar "Agregar", se agrega antes de guardar.
   */
  protected guardarZona(zonaEditada: UmbralZona): void {
    if (!this.agregarCorreo(zonaEditada)) {
      return;
    }
    const zona = this.zonas().find((z) => z.ubicacionId === zonaEditada.ubicacionId) ?? zonaEditada;
    const original = this.originales.get(zona.ubicacionId);
    const cambios: Observable<unknown>[] = [];

    for (const { variable, minimo, maximo } of VARIABLES) {
      const min = zona[minimo];
      const max = zona[maximo];
      if (original && min === original[minimo] && max === original[maximo]) {
        continue;
      }
      if (min === null || max === null) {
        this.avisar(zona, `Completa el mínimo y el máximo de ${variable.toLowerCase()}.`, true);
        return;
      }
      if (min >= max) {
        this.avisar(zona, `En ${variable.toLowerCase()}, el mínimo debe ser menor que el máximo.`, true);
        return;
      }
      cambios.push(this.servicio.guardarUmbral(zona.ubicacionId, variable, min, max));
    }
    const umbralesCambiados = cambios.length > 0;
    const correosCambiados = !original || original.correos.join(',') !== zona.correos.join(',');
    if (correosCambiados) {
      cambios.push(this.servicio.guardarResponsables(zona.ubicacionId, zona.correos));
    }

    if (cambios.length === 0) {
      this.avisar(zona, 'No hay cambios que guardar.', false);
      return;
    }

    this.guardandoZona.set(zona.ubicacionId);
    this.mensajeZona.set(null);
    forkJoin(cambios).subscribe({
      next: () => {
        this.guardandoZona.set(null);
        const partes = [
          umbralesCambiados ? 'Umbrales guardados: se aplican desde ahora a las nuevas evaluaciones.' : null,
          correosCambiados
            ? zona.correos.length ? `Responsables guardados: ${zona.correos.length}.` : 'La zona quedó sin responsables: sus alertas no enviarán correo.'
            : null,
        ];
        this.avisar(zona, partes.filter(Boolean).join(' '), false);
        this.cargarZonas();
        this.cargar();
        if (this.historial()?.ubicacionId === zona.ubicacionId) {
          this.historial.set(null); // se vuelve a abrir con las versiones nuevas
          this.verHistorial(zona);
        }
      },
      error: (error: { error?: Record<string, unknown> }) => {
        this.guardandoZona.set(null);
        this.avisar(zona, this.mensajeError(error.error), true);
        this.cargarZonas(); // si una parte se guardó y otra no, se muestra lo vigente
      },
    });
  }

  private cargarZonas(): void {
    this.servicio.umbralesPorZona().subscribe((zonas) => {
      this.originales = new Map(zonas.map((zona) => [zona.ubicacionId, { ...zona }]));
      this.zonas.set(zonas.map((zona) => ({ ...zona })));
    });
  }

  private avisar(zona: UmbralZona, texto: string, error: boolean): void {
    this.mensajeZona.set({ ubicacionId: zona.ubicacionId, texto, error });
  }

  /** Primer mensaje de error de DRF; los de correos llegan anidados por posición ({correos: {0: [...]}}). */
  private mensajeError(respuesta?: Record<string, unknown>): string {
    const primero = (valor: unknown): string | null => {
      if (typeof valor === 'string') return valor;
      if (Array.isArray(valor)) return primero(valor[0]);
      if (valor && typeof valor === 'object') return primero(Object.values(valor)[0]);
      return null;
    };
    const [campo, valor] = Object.entries(respuesta ?? {})[0] ?? [];
    const mensaje = primero(valor);
    if (!mensaje) return 'No fue posible guardar los cambios.';
    return campo === 'correos' ? `Correo no válido: ${mensaje}` : mensaje;
  }

  // ------------------------------------------------- gestión de alertas
  /** Reconocen y cierran alertas el Técnico y el Administrador. */
  protected readonly puedeGestionarAlertas = inject(AuthService).puedeModificar('administrador', 'administradorprivilegiado', 'tecnico');
  private readonly alertasService = inject(AlertasService);

  protected reconocerAlerta(alerta: Alerta): void {
    this.alertasService.reconocer(alerta.id).subscribe({
      next: (a) => this.alertas.update((lista) => lista.map((x) => (x.id === a.id ? a : x))),
      error: () => undefined,
    });
  }

  protected cerrarAlerta(alerta: Alerta): void {
    const comentario = prompt('Comentario del cierre (opcional): qué se hizo') ?? null;
    if (comentario === null) {
      return;
    }
    this.alertasService.cerrar(alerta.id, comentario).subscribe({
      next: () => this.alertas.update((lista) => lista.filter((x) => x.id !== alerta.id)),
      error: () => undefined,
    });
  }

}
