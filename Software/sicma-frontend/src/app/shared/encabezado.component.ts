import { Component, Input, inject } from '@angular/core';
import { IonBackButton, IonButtons, IonHeader, IonIcon, IonMenuButton, IonToolbar } from '@ionic/angular';
import { addIcons } from 'ionicons';
import { searchOutline } from 'ionicons/icons';
import { BuscadorService } from '../core/services/buscador.service';
import { EstadoGeneralService } from '../core/services/estado-general.service';
import { HacePipe } from './hace.pipe';

/** En Mac el atajo del buscador es ⌘ K. */
const ATAJO_BUSCADOR = /Mac|iPhone|iPad/.test(navigator.userAgent) ? '⌘ K' : 'Ctrl K';

/** Barra superior comun a las pantallas internas. */
@Component({
  selector: 'app-encabezado',
  imports: [HacePipe, IonBackButton, IonButtons, IonHeader, IonIcon, IonMenuButton, IonToolbar],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          @if (volver) {
            <ion-back-button [defaultHref]="volver" text="Volver"></ion-back-button>
          } @else {
            <ion-menu-button></ion-menu-button>
          }
        </ion-buttons>
        <div class="titulo">
          @if (seccion) {
            <span class="titulo__seccion">{{ seccion }}</span>
          }
          <h1 class="titulo__texto">{{ titulo }}</h1>
        </div>
        <!-- Buscador global (Ctrl K): abre el cuadro de búsqueda sobre la pantalla actual -->
        @if (buscador.disponible()) {
          <button
            slot="end"
            type="button"
            class="buscar"
            aria-haspopup="dialog"
            [attr.aria-keyshortcuts]="'Control+K Meta+K'"
            [attr.aria-label]="buscar + ' (' + atajo + ')'"
            (click)="buscador.abrir()"
          >
            <ion-icon name="search-outline" aria-hidden="true"></ion-icon>
            <span class="buscar__texto">{{ buscar }}</span>
            <kbd>{{ atajo }}</kbd>
          </button>
        }
        <ng-content select="[acciones]"></ng-content>
        <!-- Cuándo consultó SICMA a Zabbix por última vez (RF-INF-01) -->
        @if (estado.sincronizacion(); as s) {
          <span
            slot="end"
            class="zabbix"
            [class.zabbix--atrasado]="!s.al_dia"
            [title]="s.al_dia ? 'SICMA consulta Zabbix cada ' + s.intervalo_segundos + ' s' : 'La consulta a Zabbix está atrasada' + (s.error ? ': ' + s.error : '')"
          >
            <i aria-hidden="true"></i>
            Zabbix · {{ s.ultima_exitosa ? (s.ultima_exitosa | hace) : 'sin datos' }}
          </span>
        }
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
    .zabbix {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin: 0 14px 0 8px;
      font-size: 0.78rem;
      color: var(--sicma-tenue);
      white-space: nowrap;
    }
    .zabbix i {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--sicma-normal);
      box-shadow: 0 0 0 3px var(--sicma-normal-suave);
    }
    .zabbix--atrasado {
      color: var(--sicma-advertencia);
    }
    .zabbix--atrasado i {
      background: var(--sicma-advertencia);
      box-shadow: 0 0 0 3px var(--sicma-advertencia-suave);
    }
    .buscar {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      width: clamp(170px, 22vw, 300px);
      height: 34px;
      margin: 0 6px;
      padding: 0 6px 0 10px;
      border: 1px solid var(--sicma-linea);
      border-radius: 8px;
      background: var(--sicma-fondo);
      color: var(--sicma-tenue);
      font: inherit;
      font-size: 0.82rem;
      cursor: pointer;
    }
    .buscar:hover {
      border-color: #cdd5dc;
    }
    .buscar:focus-visible {
      outline: 2px solid var(--ion-color-primary);
      outline-offset: 2px;
    }
    .buscar ion-icon {
      flex-shrink: 0;
      font-size: 1rem;
    }
    .buscar__texto {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-align: left;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .buscar kbd {
      flex-shrink: 0;
      padding: 1px 5px;
      border: 1px solid var(--sicma-linea);
      border-radius: 4px;
      background: var(--sicma-superficie);
      font-family: var(--sicma-mono);
      font-size: 0.68rem;
    }
    /* En el teléfono no hay espacio: el estado de Zabbix se ve en Activos y el buscador queda como ícono */
    @media (max-width: 767px) {
      .zabbix {
        display: none;
      }
      .buscar {
        justify-content: center;
        width: 40px;
        padding: 0;
        border-color: transparent;
        background: transparent;
      }
      .buscar ion-icon {
        font-size: 1.3rem;
      }
      .buscar__texto,
      .buscar kbd {
        display: none;
      }
    }
  `,
})
export class EncabezadoComponent {
  protected readonly estado = inject(EstadoGeneralService);
  protected readonly buscador = inject(BuscadorService);
  protected readonly atajo = ATAJO_BUSCADOR;

  /** Texto del campo de búsqueda de la barra superior. */
  @Input() buscar = 'Buscar activo, host o evento';

  constructor() {
    addIcons({ searchOutline });
  }

  @Input({ required: true }) titulo = '';
  /** Sección del menú a la que pertenece la pantalla (Operación, Inventario, Seguridad), o su ruta. */
  @Input() seccion = '';
  /** Pantallas de detalle: muestra "Volver" (a esta ruta si no hay historial) en vez del menú. */
  @Input() volver = '';
}
