import { Component, computed, inject } from '@angular/core';
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
  idCardOutline,
  logOutOutline,
  peopleOutline,
  thermometerOutline,
  hardwareChipOutline,
  libraryOutline,
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

  private readonly opciones: ItemMenu[] = [
    { titulo: 'Panel', ruta: '/panel', icono: 'grid-outline' },
    { titulo: 'Activos', ruta: '/activos', icono: 'cube-outline' },
    { titulo: 'Monitoreo', ruta: '/monitoreo', icono: 'thermometer-outline' },
    { titulo: 'Arduinos', ruta: '/arduinos', icono: 'hardware-chip-outline' },
    { titulo: 'Catálogos', ruta: '/catalogos', icono: 'library-outline' },
    { titulo: 'Accesos', ruta: '/accesos', icono: 'key-outline' },
    { titulo: 'Personal externo', ruta: '/personal', icono: 'id-card-outline' },
    { titulo: 'Intervenciones', ruta: '/intervenciones', icono: 'build-outline' },
  ];

  /** El Departamento de contratistas solo ve su pantalla; el resto de los roles, todas. */
  protected readonly menu = computed(() => {
    if (this.auth.tieneRol('contratistas')) {
      return this.opciones.filter((o) => o.ruta === '/personal');
    }
    // El Técnico no ve el registro de accesos (información sensible).
    return this.auth.tieneRol('tecnico') ? this.opciones.filter((o) => o.ruta !== '/accesos') : this.opciones;
  });

  constructor() {
    this.auth.iniciarControlInactividad();
    addIcons({
      gridOutline,
      cubeOutline,
      thermometerOutline,
      hardwareChipOutline,
      keyOutline,
      idCardOutline,
      buildOutline,
      logOutOutline,
      peopleOutline,
      libraryOutline,
    });
  }

  protected salir(): void {
    this.auth.cerrarSesion();
    void this.router.navigate(['/login']);
  }
}
