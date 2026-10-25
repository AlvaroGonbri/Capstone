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
import { catchError, forkJoin, of } from 'rxjs';
import { ActivoInventario, EstadoSensor, EventoAcceso, Intervencion } from '../../core/models';
import { AuthService } from '../../core/services/auth.service';
import { AccesosService } from '../../core/services/accesos.service';
import { InventarioService } from '../../core/services/inventario.service';
import {
  ESTADOS_CERRADOS,
  IntervencionesService,
  etiquetaEstadoIntervencion,
  tituloIntervencion,
} from '../../core/services/intervenciones.service';
import { MonitoreoService } from '../../core/services/monitoreo.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { ColorNivelPipe } from '../../shared/nivel.pipe';

/** El backend filtra por fecha UTC: se piden desde ayer y el panel se queda con los de hoy (hora local). */
const DESDE_AYER = () => new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);

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
  private readonly inventarioService = inject(InventarioService);
  private readonly monitoreoService = inject(MonitoreoService);
  private readonly accesosService = inject(AccesosService);
  /** El Técnico no ve el registro de accesos. */
  protected readonly veAccesos = !inject(AuthService).tieneRol('tecnico');
  private readonly intervencionesService = inject(IntervencionesService);

  protected readonly cargando = signal(true);
  /** Inventario sin los retirados (RF-ACT). */
  private readonly activos = signal<ActivoInventario[]>([]);
  private readonly sensores = signal<EstadoSensor[]>([]);
  private readonly accesos = signal<EventoAcceso[]>([]);
  private readonly intervenciones = signal<Intervencion[]>([]);

  protected readonly resumen = computed(() => {
    const hoy = new Date().toDateString();
    const accesosHoy = this.accesos().filter(
      (a) => new Date(a.fecha_hora).toDateString() === hoy,
    );
    return {
      activosTotales: this.activos().length,
      activosOperativos: this.activos().filter((a) => a.estado === 'Operativo').length,
      activosEnFalla: this.activos().filter((a) => a.estado === 'Degradado' || a.estado === 'Fuera_de_servicio').length,
      sensoresEnAlerta: this.sensores().filter((s) => s.nivel !== 'normal').length,
      accesosHoy: accesosHoy.length,
      accesosDenegadosHoy: accesosHoy.filter((a) => a.resultado !== 'Permitido').length,
      intervencionesAbiertas: this.trabajosAbiertos().length,
    };
  });

  protected readonly alertas = computed(() =>
    this.sensores()
      .filter((s) => s.nivel !== 'normal')
      .sort((a, b) => b.temperatura - a.temperatura),
  );

  protected readonly trabajosAbiertos = computed(() =>
    this.intervenciones().filter((i) => !ESTADOS_CERRADOS.includes(i.estado)),
  );
  protected readonly etiquetaIntervencion = etiquetaEstadoIntervencion;
  protected readonly tituloIntervencion = tituloIntervencion;

  constructor() {
    addIcons({ alertCircleOutline, thermometerOutline, arrowForwardOutline });

    forkJoin({
      activos: this.inventarioService.listar(),
      sensores: this.monitoreoService.estadoSensores(),
      accesos: this.veAccesos
        ? this.accesosService.eventos({ desde: DESDE_AYER() }).pipe(catchError(() => of([])))
        : of([]),
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
