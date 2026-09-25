import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import {
  IonBadge,
  IonContent,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSegment,
  IonSegmentButton,
  IonSkeletonText,
} from '@ionic/angular';
import { addIcons } from 'ionicons';
import { fingerPrintOutline, idCardOutline, createOutline } from 'ionicons/icons';
import { Acceso } from '../../core/models';
import { AccesosService } from '../../core/services/accesos.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

type FiltroAcceso = 'todos' | 'autorizado' | 'denegado';

@Component({
  selector: 'app-accesos',
  imports: [
    DatePipe,
    EncabezadoComponent,
    IonBadge,
    IonContent,
    IonIcon,
    IonItem,
    IonLabel,
    IonList,
    IonNote,
    IonSegment,
    IonSegmentButton,
    IonSkeletonText,
  ],
  templateUrl: './accesos.page.html',
  styleUrl: './accesos.page.scss',
})
export class AccesosPage {
  private readonly servicio = inject(AccesosService);

  protected readonly cargando = signal(true);
  protected readonly accesos = signal<Acceso[]>([]);
  protected readonly filtro = signal<FiltroAcceso>('todos');

  protected readonly filtrados = computed(() => {
    const f = this.filtro();
    const lista = f === 'todos' ? this.accesos() : this.accesos().filter((a) => a.resultado === f);
    return [...lista].sort(
      (a, b) => new Date(b.registradoEn).getTime() - new Date(a.registradoEn).getTime(),
    );
  });

  protected readonly denegados = computed(
    () => this.accesos().filter((a) => a.resultado === 'denegado').length,
  );

  constructor() {
    addIcons({ fingerPrintOutline, idCardOutline, createOutline });
    this.servicio.listar().subscribe((lista) => {
      this.accesos.set(lista);
      this.cargando.set(false);
    });
  }

  protected icono(metodo: Acceso['metodo']): string {
    switch (metodo) {
      case 'biometrico':
        return 'finger-print-outline';
      case 'tarjeta':
        return 'id-card-outline';
      default:
        return 'create-outline';
    }
  }

  protected cambiarFiltro(valor: unknown): void {
    this.filtro.set(valor as FiltroAcceso);
  }
}
