import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';
import { excluirRolesGuard, rolGuard } from './core/guards/rol.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'panel' },
  {
    path: 'login',
    title: 'Ingreso · SICMA',
    loadComponent: () => import('./pages/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'recuperar',
    title: 'Recuperar contraseña · SICMA',
    loadComponent: () =>
      import('./pages/recuperar/recuperar.page').then((m) => m.RecuperarPage),
  },
  {
    path: 'recuperar/confirmar',
    title: 'Nueva contraseña · SICMA',
    loadComponent: () =>
      import('./pages/recuperar-confirmar/recuperar-confirmar.page').then(
        (m) => m.RecuperarConfirmarPage,
      ),
  },
  {
    path: 'cambiar-clave',
    title: 'Cambiar contraseña · SICMA',
    loadComponent: () =>
      import('./pages/cambiar-clave/cambiar-clave.page').then((m) => m.CambiarClavePage),
  },
  {
    path: 'usuarios',
    title: 'Usuarios · SICMA',
    canActivate: [authGuard, adminGuard],
    loadComponent: () => import('./pages/usuarios/usuarios.page').then((m) => m.UsuariosPage),
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
    path: 'activos/nuevo',
    title: 'Nuevo activo · SICMA',
    canActivate: [authGuard, rolGuard('administrador', 'administradorprivilegiado', 'tecnico')],
    loadComponent: () => import('./pages/activos/activo-form.page').then((m) => m.ActivoFormPage),
  },
  {
    path: 'activos/:id/editar',
    title: 'Editar activo · SICMA',
    canActivate: [authGuard, rolGuard('administrador', 'administradorprivilegiado', 'tecnico')],
    loadComponent: () => import('./pages/activos/activo-form.page').then((m) => m.ActivoFormPage),
  },
  {
    path: 'catalogos',
    title: 'Catálogos · SICMA',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/catalogos/catalogos.page').then((m) => m.CatalogosPage),
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
    path: 'arduinos',
    title: 'Arduinos · SICMA',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/arduinos/arduinos.page').then((m) => m.ArduinosPage),
  },
  {
    path: 'accesos',
    title: 'Accesos · SICMA',
    // RF-ACC-03: el registro de accesos es información sensible; no lo ve el Técnico.
    canActivate: [authGuard, excluirRolesGuard('tecnico')],
    loadComponent: () => import('./pages/accesos/accesos.page').then((m) => m.AccesosPage),
  },
  {
    path: 'personal',
    title: 'Personal externo · SICMA',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/personal/personal.page').then((m) => m.PersonalPage),
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
