import { DatePipe } from '@angular/common';
import { Component, inject, input, signal } from '@angular/core';
import {
  IonBackButton,
  IonBadge,
  IonButtons,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonHeader,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonTitle,
  IonToolbar,
} from '@ionic/angular';
import { switchMap } from 'rxjs';
import { Activo, Intervencion } from '../../core/models';
import { ActivosService } from '../../core/services/activos.service';
import { IntervencionesService } from '../../core/services/intervenciones.service';

@Component({
  selector: 'app-activo-detalle',
  imports: [
    DatePipe,
    IonBackButton,
    IonBadge,
    IonButtons,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonHeader,
    IonItem,
    IonLabel,
    IonList,
    IonNote,
    IonTitle,
    IonToolbar,
  ],
  templateUrl: './activo-detalle.page.html',
})
export class ActivoDetallePage {
  /** Llega desde la ruta gracias a withComponentInputBinding(). */
  readonly id = input.required<string>();

  private readonly activosService = inject(ActivosService);
  private readonly intervencionesService = inject(IntervencionesService);

  protected readonly activo = signal<Activo | undefined>(undefined);
  protected readonly historial = signal<Intervencion[]>([]);
  protected readonly cargando = signal(true);

  constructor() {
    queueMicrotask(() => {
      const idNumerico = Number(this.id());
      this.activosService
        .obtenerPorId(idNumerico)
        .pipe(
          switchMap((activo) => {
            this.activo.set(activo);
            return this.intervencionesService.listarPorActivo(idNumerico);
          }),
        )
        .subscribe((lista) => {
          this.historial.set(lista);
          this.cargando.set(false);
        });
    });
  }
}
