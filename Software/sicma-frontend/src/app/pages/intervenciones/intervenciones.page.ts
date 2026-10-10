import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IonBadge,
  IonContent,
  IonItem,
  IonItemDivider,
  IonItemGroup,
  IonLabel,
  IonList,
  IonSegment,
  IonSegmentButton,
  IonSkeletonText,
} from '@ionic/angular';
import { EstadoIntervencion, Intervencion } from '../../core/models';
import { IntervencionesService } from '../../core/services/intervenciones.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

type FiltroIntervencion = 'todas' | EstadoIntervencion;

@Component({
  selector: 'app-intervenciones',
  imports: [
    DatePipe,
    RouterLink,
    EncabezadoComponent,
    IonBadge,
    IonContent,
    IonItem,
    IonItemDivider,
    IonItemGroup,
    IonLabel,
    IonList,
    IonSegment,
    IonSegmentButton,
    IonSkeletonText,
  ],
  templateUrl: './intervenciones.page.html',
  styleUrl: './intervenciones.page.scss',
})
export class IntervencionesPage {
  private readonly servicio = inject(IntervencionesService);

  protected readonly cargando = signal(true);
  protected readonly intervenciones = signal<Intervencion[]>([]);
  protected readonly filtro = signal<FiltroIntervencion>('todas');

  protected readonly filtradas = computed(() => {
    const f = this.filtro();
    const lista =
      f === 'todas' ? this.intervenciones() : this.intervenciones().filter((i) => i.estado === f);
    return [...lista].sort(
      (a, b) => new Date(b.iniciadaEn).getTime() - new Date(a.iniciadaEn).getTime(),
    );
  });

  constructor() {
    this.servicio.listar().subscribe((lista) => {
      this.intervenciones.set(lista);
      this.cargando.set(false);
    });
  }

  protected colorEstado(estado: EstadoIntervencion): string {
    switch (estado) {
      case 'en curso':
        return 'warning';
      case 'planificada':
        return 'primary';
      default:
        return 'medium';
    }
  }

  protected cambiarFiltro(valor: unknown): void {
    this.filtro.set(valor as FiltroIntervencion);
  }
}
