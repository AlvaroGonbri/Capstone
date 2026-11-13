import { Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import {
  IonApp,
  IonButton,
  IonContent,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonMenu,
  IonMenuToggle,
  IonRouterOutlet,
  IonSplitPane,
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

type GrupoMenu = 'Operación' | 'Inventario' | 'Seguridad';

interface ItemMenu {
  titulo: string;
  ruta: string;
  icono: string;
  grupo: GrupoMenu;
  /** Nombre corto para la barra de pestañas de la app móvil. */
  tituloCorto?: string;
}

const ORDEN_GRUPOS: GrupoMenu[] = ['Operación', 'Inventario', 'Seguridad'];

/** Pestañas de la app móvil (solo consulta), en este orden. */
const RUTAS_PESTANAS = ['/panel', '/activos', '/monitoreo', '/intervenciones'];

@Component({
  selector: 'app-root',
  imports: [
    RouterLink,
    RouterLinkActive,
    IonApp,
    IonButton,
    IonContent,
    IonIcon,
    IonItem,
    IonLabel,
    IonList,
    IonMenu,
    IonMenuToggle,
    IonRouterOutlet,
    IonSplitPane,
  ],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  private readonly opciones: ItemMenu[] = [
    { titulo: 'Panel', ruta: '/panel', icono: 'grid-outline', grupo: 'Operación' },
    { titulo: 'Activos', ruta: '/activos', icono: 'cube-outline', grupo: 'Inventario' },
    { titulo: 'Monitoreo', ruta: '/monitoreo', icono: 'thermometer-outline', grupo: 'Operación', tituloCorto: 'Ambiente' },
    { titulo: 'Arduinos', ruta: '/arduinos', icono: 'hardware-chip-outline', grupo: 'Inventario' },
    { titulo: 'Catálogos', ruta: '/catalogos', icono: 'library-outline', grupo: 'Inventario' },
    { titulo: 'Accesos', ruta: '/accesos', icono: 'key-outline', grupo: 'Seguridad' },
    { titulo: 'Personal externo', ruta: '/personal', icono: 'id-card-outline', grupo: 'Seguridad', tituloCorto: 'Personal' },
    { titulo: 'Intervenciones', ruta: '/intervenciones', icono: 'build-outline', grupo: 'Operación', tituloCorto: 'Trabajos' },
  ];

  private readonly opcionUsuarios: ItemMenu = {
    titulo: 'Usuarios',
    ruta: '/usuarios',
    icono: 'people-outline',
    grupo: 'Seguridad',
  };

  /** El Departamento de contratistas solo ve su pantalla; el resto de los roles, todas. */
  protected readonly menu = computed(() => {
    if (this.auth.tieneRol('contratistas')) {
      return this.opciones.filter((o) => o.ruta === '/personal');
    }
    // El Técnico no ve el registro de accesos (información sensible).
    return this.auth.tieneRol('tecnico') ? this.opciones.filter((o) => o.ruta !== '/accesos') : this.opciones;
  });

  /** Menú lateral agrupado. Usuarios aparece con la misma condición de antes. */
  protected readonly secciones = computed(() => {
    const items = [...this.menu()];
    if (this.auth.puedeModificar('administrador', 'administradorprivilegiado')) {
      items.push(this.opcionUsuarios);
    }
    return ORDEN_GRUPOS.map((titulo) => ({
      titulo,
      items: items.filter((i) => i.grupo === titulo),
    })).filter((s) => s.items.length > 0);
  });

  /** App móvil: pestañas inferiores con las secciones de consulta que el rol puede ver. */
  protected readonly pestanas = computed(() => {
    const visibles = this.menu().filter((i) => RUTAS_PESTANAS.includes(i.ruta));
    const ordenadas = RUTAS_PESTANAS.map((r) => visibles.find((i) => i.ruta === r)).filter(
      (i): i is ItemMenu => !!i,
    );
    // Si el rol no ve ninguna de esas secciones (p. ej. contratistas), se muestran las suyas.
    return ordenadas.length > 0 ? ordenadas : this.menu();
  });

  protected readonly pestanasVisibles = computed(
    () => this.auth.soloConsulta && this.auth.autenticado(),
  );

  protected readonly iniciales = computed(() => {
    const nombre = (this.auth.usuario()?.nombre ?? '').trim();
    const partes = nombre.split(/\s+/).filter(Boolean);
    if (partes.length === 0) return '·';
    if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
    return (partes[0][0] + partes[1][0]).toUpperCase();
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
