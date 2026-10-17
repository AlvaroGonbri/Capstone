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
  IonItem,
  IonLabel,
  IonNote,
  IonSpinner,
} from '@ionic/angular';
import { Arduino } from '../../core/models';
import { ArduinosService } from '../../core/services/arduinos.service';
import { rangoTexto } from '../../core/services/umbrales.util';
import { EncabezadoComponent } from '../../shared/encabezado.component';

@Component({
  selector: 'app-arduinos',
  imports: [
    DatePipe,
    RouterLink,
    EncabezadoComponent,
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonItem,
    IonLabel,
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
