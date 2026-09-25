import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IonBadge,
  IonContent,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSearchbar,
  IonSegment,
  IonSegmentButton,
  IonSkeletonText,
} from '@ionic/angular';
import { Activo, EstadoActivo } from '../../core/models';
import { ActivosService } from '../../core/services/activos.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

type FiltroEstado = 'todos' | EstadoActivo;

@Component({
  selector: 'app-activos',
  imports: [
    RouterLink,
    EncabezadoComponent,
    IonBadge,
    IonContent,
    IonItem,
    IonLabel,
    IonList,
    IonNote,
    IonSearchbar,
    IonSegment,
    IonSegmentButton,
    IonSkeletonText,
  ],
  templateUrl: './activos.page.html',
  styleUrl: './activos.page.scss',
})
export class ActivosPage {
  private readonly servicio = inject(ActivosService);

  protected readonly cargando = signal(true);
  protected readonly activos = signal<Activo[]>([]);
  protected readonly busqueda = signal('');
  protected readonly filtro = signal<FiltroEstado>('todos');

  protected readonly filtrados = computed(() => {
    const texto = this.busqueda().trim().toLowerCase();
    const estado = this.filtro();
    return this.activos().filter((a) => {
      const coincideEstado = estado === 'todos' || a.estado === estado;
      const coincideTexto =
        texto === '' ||
        [a.codigo, a.nombre, a.marca, a.modelo, a.rack, a.numeroSerie, a.responsable]
          .join(' ')
          .toLowerCase()
          .includes(texto);
      return coincideEstado && coincideTexto;
    });
  });

  constructor() {
    this.servicio.listar().subscribe((lista) => {
      this.activos.set(lista);
      this.cargando.set(false);
    });
  }

  protected colorEstado(estado: EstadoActivo): string {
    switch (estado) {
      case 'operativo':
        return 'success';
      case 'en mantencion':
        return 'warning';
      case 'en falla':
        return 'danger';
      default:
        return 'medium';
    }
  }

  protected cambiarBusqueda(valor: string | null | undefined): void {
    this.busqueda.set(valor ?? '');
  }

  protected cambiarFiltro(valor: unknown): void {
    this.filtro.set(valor as FiltroEstado);
  }
}
