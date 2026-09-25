import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'panel' },
  {
    path: 'login',
    title: 'Ingreso · SICMA',
    loadComponent: () => import('./pages/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'panel',
    title: 'Panel · SICMA',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/panel/panel.page').then((m) => m.PanelPage),
  },
  {
    path: 'activos',
    title: 'Activos · SICMA',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/activos/activos.page').then((m) => m.ActivosPage),
  },
  {
    path: 'activos/:id',
    title: 'Ficha de activo · SICMA',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/activos/activo-detalle.page').then((m) => m.ActivoDetallePage),
  },
  {
    path: 'monitoreo',
    title: 'Monitoreo ambiental · SICMA',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/monitoreo/monitoreo.page').then((m) => m.MonitoreoPage),
  },
  {
    path: 'accesos',
    title: 'Accesos · SICMA',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/accesos/accesos.page').then((m) => m.AccesosPage),
  },
  {
    path: 'intervenciones',
    title: 'Intervenciones · SICMA',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/intervenciones/intervenciones.page').then((m) => m.IntervencionesPage),
  },
  { path: '**', redirectTo: 'panel' },
];
