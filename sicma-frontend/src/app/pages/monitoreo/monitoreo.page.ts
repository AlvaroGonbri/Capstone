import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import {
  IonBadge,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardSubtitle,
  IonCardTitle,
  IonContent,
  IonNote,
  IonRefresher,
  IonRefresherContent,
  IonSkeletonText,
} from '@ionic/angular';
import { EstadoSensor, Umbrales } from '../../core/models';
import { MonitoreoService } from '../../core/services/monitoreo.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { ColorNivelPipe } from '../../shared/nivel.pipe';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-monitoreo',
  imports: [
    DatePipe,
    EncabezadoComponent,
    ColorNivelPipe,
    IonBadge,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardSubtitle,
    IonCardTitle,
    IonContent,
    IonNote,
    IonRefresher,
    IonRefresherContent,
    IonSkeletonText,
  ],
  templateUrl: './monitoreo.page.html',
  styleUrl: './monitoreo.page.scss',
})
export class MonitoreoPage {
  private readonly servicio = inject(MonitoreoService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly cargando = signal(true);
  protected readonly sensores = signal<EstadoSensor[]>([]);
  protected readonly umbrales = signal<Umbrales | null>(null);
  protected readonly actualizadoEn = signal<Date>(new Date());

  protected readonly enAlerta = computed(() =>
    this.sensores().filter((s) => s.nivel !== 'normal').length,
  );

  constructor() {
    this.cargar();
    this.servicio.umbrales().subscribe((u) => this.umbrales.set(u));

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
