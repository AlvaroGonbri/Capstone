import { Component, Input } from '@angular/core';
import { IonButtons, IonHeader, IonMenuButton, IonToolbar } from '@ionic/angular';

/** Barra superior comun a las pantallas internas. */
@Component({
  selector: 'app-encabezado',
  imports: [IonButtons, IonHeader, IonMenuButton, IonToolbar],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-menu-button></ion-menu-button>
        </ion-buttons>
        <div class="titulo">
          @if (seccion) {
            <span class="titulo__seccion">{{ seccion }}</span>
          }
          <h1 class="titulo__texto">{{ titulo }}</h1>
        </div>
        <ng-content select="[acciones]"></ng-content>
      </ion-toolbar>
    </ion-header>
  `,
  styles: `
    .titulo {
      padding: 0 12px;
      min-width: 0;
    }
    .titulo__seccion {
      display: block;
      font-size: 0.72rem;
      color: var(--sicma-tenue);
      line-height: 1.2;
    }
    .titulo__texto {
      margin: 0;
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      line-height: 1.25;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  `,
})
export class EncabezadoComponent {
  @Input({ required: true }) titulo = '';
  /** Sección del menú a la que pertenece la pantalla (Operación, Inventario, Seguridad). */
  @Input() seccion = '';
}
