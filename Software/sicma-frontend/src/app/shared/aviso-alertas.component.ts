import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { IonButton, IonIcon, IonModal } from '@ionic/angular';
import { addIcons } from 'ionicons';
import { closeOutline, warningOutline } from 'ionicons/icons';
import { catchError, map, of } from 'rxjs';
import { Alerta } from '../core/models';
import { AlertasService } from '../core/services/alertas.service';
import { AuthService } from '../core/services/auth.service';
import { AvisoAlertasService } from '../core/services/aviso-alertas.service';
import { InventarioService } from '../core/services/inventario.service';
import { HacePipe } from './hace.pipe';

/** Alertas que se listan en el aviso; si llegan más, se indica cuántas y se enlaza al Panel. */
const MAXIMO_VISIBLE = 4;

type Nivel = 'critico' | 'advertencia' | 'info';

const SEVERIDADES: Record<Alerta['severidad'], { etiqueta: string; nivel: Nivel; rango: number }> = {
  Critica: { etiqueta: 'Crítica', nivel: 'critico', rango: 0 },
  Alta: { etiqueta: 'Alta', nivel: 'critico', rango: 1 },
  Advertencia: { etiqueta: 'Advertencia', nivel: 'advertencia', rango: 2 },
  Informativa: { etiqueta: 'Informativa', nivel: 'info', rango: 3 },
};

/**
 * Ventana emergente que avisa al instante de las alertas nuevas, esté donde esté el usuario.
 * Desde aquí se puede reconocer la alerta (Técnico y Administradores, en la web) o ir a verla.
 */
@Component({
  selector: 'app-aviso-alertas',
  imports: [IonModal, IonButton, IonIcon, HacePipe],
  template: `
    <ion-modal
      class="aviso-alertas"
      [isOpen]="abierto()"
      aria-labelledby="aviso-alertas-titulo"
      (didDismiss)="servicio.descartar()"
    >
      <ng-template>
        <div class="aviso" [attr.data-nivel]="nivelMayor()">
          <header class="aviso__cabecera">
            <span class="aviso__icono" aria-hidden="true"><ion-icon name="warning-outline"></ion-icon></span>
            <div class="aviso__titulos">
              <h2 id="aviso-alertas-titulo">{{ titulo() }}</h2>
              <p>{{ nota() }}</p>
            </div>
            <button type="button" class="aviso__cerrar" (click)="cerrar()" aria-label="Cerrar el aviso">
              <ion-icon name="close-outline" aria-hidden="true"></ion-icon>
            </button>
          </header>

          <ul class="aviso__lista">
            @for (a of visibles(); track a.id) {
              <li class="alerta" [attr.data-nivel]="nivel(a)">
                <div class="alerta__meta">
                  <span class="chip" [attr.data-nivel]="nivel(a)">{{ severidad(a) }}</span>
                  <span>{{ origen(a) }}</span>
                  <span class="alerta__hora">{{ a.fecha_apertura | hace }}</span>
                </div>
                <p class="alerta__problema">{{ a.problema || a.condicion }}</p>
                <div class="alerta__acciones">
                  @if (a.estado === 'Reconocida') {
                    <span class="alerta__gestion">
                      Reconocida{{ a.ultima_gestion?.usuario ? ' por ' + a.ultima_gestion?.usuario : '' }}
                    </span>
                  } @else if (puedeGestionar) {
                    <ion-button size="small" (click)="reconocer(a)" [disabled]="reconociendo().has(a.id)">
                      Reconocer
                    </ion-button>
                  }
                  <ion-button size="small" fill="outline" (click)="ver(a)">Ver</ion-button>
                  @if (fallidas().has(a.id)) {
                    <span class="alerta__error" role="status">No fue posible reconocerla; inténtalo desde el Panel.</span>
                  }
                </div>
              </li>
            }
          </ul>

          <footer class="aviso__pie">
            @if (ocultas() > 0) {
              <button type="button" class="aviso__mas" (click)="irA(['/panel'])">
                y {{ ocultas() }} {{ ocultas() === 1 ? 'alerta más' : 'alertas más' }} · ver en el Panel
              </button>
            }
            <ion-button fill="clear" (click)="cerrar()">Entendido</ion-button>
          </footer>
        </div>
      </ng-template>
    </ion-modal>
  `,
  styles: `
    .aviso {
      --acento: var(--sicma-info);
      --acento-suave: var(--sicma-info-suave);
      display: flex;
      flex-direction: column;
      align-items: stretch;
      max-height: calc(100vh - 48px);
      border-top: 4px solid var(--acento);
      background: var(--sicma-superficie);
      color: var(--sicma-tinta);

      &[data-nivel='critico'] { --acento: var(--sicma-critico); --acento-suave: var(--sicma-critico-suave); }
      &[data-nivel='advertencia'] { --acento: var(--sicma-advertencia); --acento-suave: var(--sicma-advertencia-suave); }
    }

    .aviso__cabecera {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px 16px 12px 18px;
    }

    .aviso__icono {
      display: grid;
      place-items: center;
      flex-shrink: 0;
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: var(--acento-suave);
      color: var(--acento);
      font-size: 21px;
    }

    .aviso__titulos {
      flex: 1;
      min-width: 0;

      h2 {
        margin: 1px 0 3px;
        font-size: 1.05rem;
        font-weight: 700;
      }

      p {
        margin: 0;
        font-size: 0.78rem;
        line-height: 1.4;
        color: var(--sicma-tenue);
      }
    }

    .aviso__cerrar {
      display: grid;
      place-items: center;
      flex-shrink: 0;
      width: 32px;
      height: 32px;
      margin: -4px -6px 0 0;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: var(--sicma-tenue);
      font-size: 20px;
      cursor: pointer;

      &:hover { background: var(--sicma-linea-suave); color: var(--sicma-tinta); }
      &:focus-visible { outline: 2px solid var(--ion-color-primary); outline-offset: 1px; }
    }

    .aviso__lista {
      flex: 1;
      min-height: 0;
      margin: 0;
      padding: 0 16px;
      overflow-y: auto;
      list-style: none;
    }

    .alerta {
      padding: 12px 0;
      border-top: 1px solid var(--sicma-linea-suave);
    }

    .alerta__meta {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px 10px;
      font-size: 0.76rem;
      color: var(--sicma-tinta-2, var(--sicma-tenue));
    }

    .alerta__hora {
      margin-left: auto;
      color: var(--sicma-tenue);
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 9px;
      border-radius: 999px;
      background: var(--sicma-info-suave);
      color: var(--sicma-tinta);
      font-size: 0.7rem;
      font-weight: 600;

      &::before {
        content: '';
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--sicma-info);
      }

      &[data-nivel='critico'] { background: var(--sicma-critico-suave); &::before { background: var(--sicma-critico); } }
      &[data-nivel='advertencia'] { background: var(--sicma-advertencia-suave); &::before { background: var(--sicma-advertencia); } }
    }

    .alerta__problema {
      margin: 7px 0 9px;
      font-size: 0.92rem;
      font-weight: 600;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }

    .alerta__acciones {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px 8px;

      ion-button { margin: 0; }
    }

    .alerta__gestion {
      font-size: 0.78rem;
      color: var(--sicma-normal);
    }

    .alerta__error {
      flex-basis: 100%;
      font-size: 0.76rem;
      color: var(--sicma-critico);
    }

    .aviso__pie {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
      gap: 4px 12px;
      padding: 8px 10px 10px 16px;
      border-top: 1px solid var(--sicma-linea-suave);
    }

    .aviso__mas {
      margin-right: auto;
      padding: 4px 0;
      border: 0;
      background: none;
      color: var(--ion-color-primary);
      font: inherit;
      font-size: 0.8rem;
      cursor: pointer;

      &:hover { text-decoration: underline; }
    }
  `,
})
export class AvisoAlertasComponent {
  protected readonly servicio = inject(AvisoAlertasService);
  private readonly alertas = inject(AlertasService);
  private readonly inventario = inject(InventarioService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  /** Reconocen alertas el Técnico y los Administradores (la app móvil es solo de consulta). */
  protected readonly puedeGestionar = this.auth.puedeModificar('administrador', 'administradorprivilegiado', 'tecnico');
  protected readonly reconociendo = signal(new Set<number>());
  protected readonly fallidas = signal(new Set<number>());

  protected readonly abierto = computed(() => this.servicio.nuevas().length > 0);

  /** Primero las más graves; a igual severidad, la más reciente. */
  private readonly ordenadas = computed(() =>
    [...this.servicio.nuevas()].sort(
      (a, b) => SEVERIDADES[a.severidad].rango - SEVERIDADES[b.severidad].rango || b.id - a.id,
    ),
  );
  protected readonly visibles = computed(() => this.ordenadas().slice(0, MAXIMO_VISIBLE));
  protected readonly ocultas = computed(() => Math.max(0, this.ordenadas().length - MAXIMO_VISIBLE));

  protected readonly titulo = computed(() => {
    const n = this.servicio.nuevas().length;
    return n === 1 ? 'Nueva alerta' : `${n} alertas nuevas`;
  });

  protected readonly nota = computed(() =>
    this.servicio.nuevas().length === 1
      ? 'Cerrar este aviso no cierra la alerta: sigue en el Panel.'
      : 'Cerrar este aviso no cierra las alertas: siguen en el Panel.',
  );

  protected readonly nivelMayor = computed<Nivel>(() => {
    const primera = this.ordenadas()[0];
    return primera ? SEVERIDADES[primera.severidad].nivel : 'info';
  });

  constructor() {
    addIcons({ warningOutline, closeOutline });
  }

  protected nivel(a: Alerta): Nivel {
    return SEVERIDADES[a.severidad]?.nivel ?? 'info';
  }

  protected severidad(a: Alerta): string {
    return SEVERIDADES[a.severidad]?.etiqueta ?? a.severidad;
  }

  protected origen(a: Alerta): string {
    switch (a.origen) {
      case 'Zabbix':
        return ['Servidor', a.host].filter(Boolean).join(' · ');
      case 'IoT':
        return ['Ambiente', a.sensor_codigo].filter(Boolean).join(' · ');
      default:
        return 'Control de acceso';
    }
  }

  protected reconocer(a: Alerta): void {
    this.reconociendo.update((s) => new Set(s).add(a.id));
    this.fallidas.update((s) => this.sin(s, a.id));
    this.alertas.reconocer(a.id).subscribe({
      next: (actualizada) => {
        this.reconociendo.update((s) => this.sin(s, a.id));
        this.servicio.actualizar(actualizada);
      },
      error: () => {
        this.reconociendo.update((s) => this.sin(s, a.id));
        this.fallidas.update((s) => new Set(s).add(a.id));
      },
    });
  }

  /** Lleva a donde se gestiona: la ficha del servidor (si está inventariado), Monitoreo o Accesos. */
  protected ver(a: Alerta): void {
    if (a.origen === 'IoT') {
      this.irA(['/monitoreo']);
    } else if (a.origen === 'Biometria') {
      this.irA([this.auth.tieneRol('tecnico') ? '/panel' : '/accesos']);
    } else {
      const host = a.host?.toLowerCase();
      this.inventario
        .listar()
        .pipe(
          map((activos) => activos.find((x) => host && x.codigo.toLowerCase() === host)),
          catchError(() => of(undefined)),
        )
        .subscribe((activo) => this.irA(activo ? ['/activos', activo.id] : ['/activos']));
    }
  }

  protected irA(ruta: (string | number)[]): void {
    this.cerrar();
    void this.router.navigate(ruta);
  }

  protected cerrar(): void {
    this.servicio.descartar();
    this.fallidas.set(new Set());
  }

  private sin(conjunto: Set<number>, id: number): Set<number> {
    const copia = new Set(conjunto);
    copia.delete(id);
    return copia;
  }
}
