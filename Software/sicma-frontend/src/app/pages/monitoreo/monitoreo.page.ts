import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardSubtitle,
  IonCardTitle,
  IonContent,
  IonInput,
  IonNote,
  IonRefresher,
  IonRefresherContent,
  IonSkeletonText,
  IonSpinner,
  IonTextarea,
} from '@ionic/angular';
import { Observable, forkJoin } from 'rxjs';
import { Alerta, EstadoSensor, UmbralZona, Umbrales } from '../../core/models';
import { AuthService } from '../../core/services/auth.service';
import { MonitoreoService, VariableAmbiental } from '../../core/services/monitoreo.service';
import { rangoTexto } from '../../core/services/umbrales.util';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { ColorNivelPipe } from '../../shared/nivel.pipe';
import { environment } from '../../../environments/environment';

type CampoUmbral = keyof Umbrales;

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
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardSubtitle,
    IonCardTitle,
    IonContent,
    IonInput,
    IonNote,
    IonRefresher,
    IonRefresherContent,
    IonSkeletonText,
    IonSpinner,
    IonTextarea,
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

  protected readonly enAlerta = computed(() =>
    this.sensores().filter((s) => s.nivel !== 'normal').length,
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

  protected guardarZona(zona: UmbralZona): void {
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

    if (cambios.length === 0) {
      this.avisar(zona, 'No hay cambios que guardar.', false);
      return;
    }

    this.guardandoZona.set(zona.ubicacionId);
    this.mensajeZona.set(null);
    forkJoin(cambios).subscribe({
      next: () => {
        this.guardandoZona.set(null);
        this.avisar(zona, 'Umbrales guardados. Se aplican desde ahora a las nuevas evaluaciones.', false);
        this.cargarZonas();
        this.cargar();
      },
      error: (error: { error?: Record<string, string | string[]> }) => {
        this.guardandoZona.set(null);
        this.avisar(zona, this.mensajeError(error.error), true);
        this.cargarZonas(); // si una variable se guardó y la otra no, se muestra lo vigente
      },
    });
  }

  /** Los correos se escriben separados por coma, punto y coma o salto de línea. */
  protected editarCorreos(zona: UmbralZona, texto: string | null | undefined): void {
    const correos = (texto ?? '').split(/[\s,;]+/).map((c) => c.trim()).filter(Boolean);
    this.zonas.update((lista) =>
      lista.map((item) => (item.ubicacionId === zona.ubicacionId ? { ...item, correos } : item)),
    );
  }

  protected guardarResponsables(zona: UmbralZona): void {
    this.guardandoZona.set(zona.ubicacionId);
    this.mensajeZona.set(null);
    this.servicio.guardarResponsables(zona.ubicacionId, zona.correos).subscribe({
      next: ({ correos }) => {
        this.guardandoZona.set(null);
        this.avisar(
          zona,
          correos.length ? `Responsables guardados: ${correos.length}.` : 'La zona quedó sin responsables: sus alertas no enviarán correo.',
          false,
        );
        this.cargarZonas();
      },
      error: (error: { error?: Record<string, unknown> }) => {
        this.guardandoZona.set(null);
        const correos = error.error?.['correos'];
        const detalle = correos && typeof correos === 'object' ? Object.values(correos).flat()[0] : null;
        this.avisar(zona, typeof detalle === 'string' ? `Correo no válido: ${detalle}` : 'No fue posible guardar los responsables.', true);
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

  private mensajeError(respuesta?: Record<string, string | string[]>): string {
    const [, mensajes] = Object.entries(respuesta ?? {})[0] ?? [];
    const mensaje = Array.isArray(mensajes) ? mensajes[0] : mensajes;
    return mensaje ?? 'No fue posible guardar los umbrales.';
  }

  /** Convierte el historial de temperatura en los puntos de una linea de 120x36. */
  protected puntos(historial: number[]): string {
    if (historial.length < 2) {
      return '';
    }
    const minimo = Math.min(...historial);
    const maximo = Math.max(...historial);
    const rango = maximo - minimo || 1;
    const anchoPaso = 120 / (historial.length - 1);
    return historial
      .map((valor, i) => {
        const x = (i * anchoPaso).toFixed(1);
        const y = (32 - ((valor - minimo) / rango) * 28).toFixed(1);
        return `${x},${y}`;
      })
      .join(' ');
  }
}
