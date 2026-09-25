import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IonBadge,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSkeletonText,
} from '@ionic/angular';
import { addIcons } from 'ionicons';
import { alertCircleOutline, arrowForwardOutline, thermometerOutline } from 'ionicons/icons';
import { forkJoin } from 'rxjs';
import { Acceso, Activo, EstadoSensor, Intervencion } from '../../core/models';
import { AccesosService } from '../../core/services/accesos.service';
import { ActivosService } from '../../core/services/activos.service';
import { IntervencionesService } from '../../core/services/intervenciones.service';
import { MonitoreoService } from '../../core/services/monitoreo.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { ColorNivelPipe } from '../../shared/nivel.pipe';

@Component({
  selector: 'app-panel',
  imports: [
    DatePipe,
    RouterLink,
    EncabezadoComponent,
    ColorNivelPipe,
    IonBadge,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonIcon,
    IonItem,
    IonLabel,
    IonList,
    IonNote,
    IonSkeletonText,
  ],
  templateUrl: './panel.page.html',
  styleUrl: './panel.page.scss',
})
export class PanelPage {
  private readonly activosService = inject(ActivosService);
  private readonly monitoreoService = inject(MonitoreoService);
  private readonly accesosService = inject(AccesosService);
  private readonly intervencionesService = inject(IntervencionesService);

  protected readonly cargando = signal(true);
  private readonly activos = signal<Activo[]>([]);
  private readonly sensores = signal<EstadoSensor[]>([]);
  private readonly accesos = signal<Acceso[]>([]);
  private readonly intervenciones = signal<Intervencion[]>([]);

  protected readonly resumen = computed(() => {
    const hoy = new Date().toDateString();
    const accesosHoy = this.accesos().filter(
      (a) => new Date(a.registradoEn).toDateString() === hoy,
    );
    return {
      activosTotales: this.activos().length,
      activosOperativos: this.activos().filter((a) => a.estado === 'operativo').length,
      activosEnFalla: this.activos().filter((a) => a.estado === 'en falla').length,
      sensoresEnAlerta: this.sensores().filter((s) => s.nivel !== 'normal').length,
      accesosHoy: accesosHoy.length,
      accesosDenegadosHoy: accesosHoy.filter((a) => a.resultado === 'denegado').length,
      intervencionesAbiertas: this.intervenciones().filter((i) => i.estado !== 'cerrada').length,
    };
  });

  protected readonly alertas = computed(() =>
    this.sensores()
      .filter((s) => s.nivel !== 'normal')
      .sort((a, b) => b.temperatura - a.temperatura),
  );

  protected readonly trabajosAbiertos = computed(() =>
    this.intervenciones().filter((i) => i.estado !== 'cerrada'),
  );

  constructor() {
    addIcons({ alertCircleOutline, thermometerOutline, arrowForwardOutline });

    forkJoin({
      activos: this.activosService.listar(),
      sensores: this.monitoreoService.estadoSensores(),
      accesos: this.accesosService.listar(),
      intervenciones: this.intervencionesService.listar(),
    }).subscribe((datos) => {
      this.activos.set(datos.activos);
      this.sensores.set(datos.sensores);
      this.accesos.set(datos.accesos);
      this.intervenciones.set(datos.intervenciones);
      this.cargando.set(false);
    });
  }
}
