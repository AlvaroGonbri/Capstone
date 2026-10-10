import { Component, Input } from '@angular/core';
import { IonButtons, IonHeader, IonMenuButton, IonTitle, IonToolbar } from '@ionic/angular';

/** Barra superior comun a las pantallas internas. */
@Component({
  selector: 'app-encabezado',
  imports: [IonButtons, IonHeader, IonMenuButton, IonTitle, IonToolbar],
  template: `
    <ion-header>
      <ion-toolbar color="primary">
        <ion-buttons slot="start">
          <ion-menu-button></ion-menu-button>
        </ion-buttons>
        <ion-title>{{ titulo }}</ion-title>
        <ng-content select="[acciones]"></ng-content>
      </ion-toolbar>
    </ion-header>
  `,
})
export class EncabezadoComponent {
  @Input({ required: true }) titulo = '';
}
