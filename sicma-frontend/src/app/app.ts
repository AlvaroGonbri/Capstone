import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import {
  IonApp,
  IonContent,
  IonHeader,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonMenu,
  IonMenuToggle,
  IonNote,
  IonRouterOutlet,
  IonSplitPane,
  IonTitle,
  IonToolbar,
} from '@ionic/angular';
import { addIcons } from 'ionicons';
import {
  buildOutline,
  cubeOutline,
  gridOutline,
  keyOutline,
  logOutOutline,
  thermometerOutline,
} from 'ionicons/icons';
import { AuthService } from './core/services/auth.service';

interface ItemMenu {
  titulo: string;
  ruta: string;
  icono: string;
}

@Component({
  selector: 'app-root',
  imports: [
    RouterLink,
    RouterLinkActive,
    IonApp,
    IonContent,
    IonHeader,
    IonIcon,
    IonItem,
    IonLabel,
    IonList,
    IonMenu,
    IonMenuToggle,
    IonNote,
    IonRouterOutlet,
    IonSplitPane,
    IonTitle,
    IonToolbar,
  ],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly menu: ItemMenu[] = [
    { titulo: 'Panel', ruta: '/panel', icono: 'grid-outline' },
    { titulo: 'Activos', ruta: '/activos', icono: 'cube-outline' },
    { titulo: 'Monitoreo', ruta: '/monitoreo', icono: 'thermometer-outline' },
    { titulo: 'Accesos', ruta: '/accesos', icono: 'key-outline' },
    { titulo: 'Intervenciones', ruta: '/intervenciones', icono: 'build-outline' },
  ];

  constructor() {
    addIcons({
      gridOutline,
      cubeOutline,
      thermometerOutline,
      keyOutline,
      buildOutline,
      logOutOutline,
    });
  }

  protected salir(): void {
    this.auth.cerrarSesion();
    void this.router.navigate(['/login']);
  }
}
