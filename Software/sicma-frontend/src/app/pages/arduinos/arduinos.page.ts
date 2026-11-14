import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonNote,
  IonSpinner,
} from '@ionic/angular';
import { Arduino } from '../../core/models';
import { ArduinosService } from '../../core/services/arduinos.service';
import { posicionesBarra, rangoTexto, respectoDelRango } from '../../core/services/umbrales.util';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { HacePipe } from '../../shared/hace.pipe';

@Component({
  selector: 'app-arduinos',
  imports: [
    DatePipe,
    RouterLink,
    EncabezadoComponent,
    HacePipe,
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonNote,
    IonSpinner,
  ],
  templateUrl: './arduinos.page.html',
  styleUrl: './arduinos.page.scss',
})
export class ArduinosPage {
  private readonly servicio = inject(ArduinosService);

  protected readonly cargando = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly arduinos = signal<Arduino[]>([]);
  protected readonly rango = rangoTexto;
  protected readonly barra = posicionesBarra;

  /** Fuera de rango según los umbrales de su zona (solo presentación; la evaluación la hace el backend). */
  protected fuera(valor: number, minimo: number | null | undefined, maximo: number | null | undefined): boolean {
    return respectoDelRango(valor, minimo ?? null, maximo ?? null) !== null;
  }

  constructor() {
    this.servicio.listar().subscribe({
      next: (lista) => {
        this.arduinos.set(lista);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No fue posible cargar los controladores ambientales.');
        this.cargando.set(false);
      },
    });
  }
}
