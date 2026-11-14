import { Component, ElementRef, computed, effect, inject, signal, untracked, viewChild } from '@angular/core';
import { Router } from '@angular/router';
import { IonIcon } from '@ionic/angular';
import { addIcons } from 'ionicons';
import { searchOutline } from 'ionicons/icons';
import { Subscription } from 'rxjs';
import { BuscadorService, ElementoBusqueda, TIPOS_BUSQUEDA, normalizar } from '../core/services/buscador.service';

/** Resultados que se muestran por grupo (Activos, Servidores, …). */
const POR_GRUPO = 5;

type Resultado = ElementoBusqueda & { posicion: number };

/**
 * Buscador global: se abre con Ctrl K (⌘ K en Mac) o con el campo de la barra superior.
 * ↑ ↓ recorren los resultados, Enter abre el elegido y Esc cierra.
 */
@Component({
  selector: 'app-buscador',
  imports: [IonIcon],
  host: { '(document:keydown)': 'atajo($event)' },
  template: `
    @if (servicio.abierto()) {
      <div class="fondo" (click)="cerrar()" aria-hidden="true"></div>
      <div class="buscador" role="dialog" aria-modal="true" aria-label="Buscar en SICMA">
        <div class="buscador__campo">
          <ion-icon name="search-outline" aria-hidden="true"></ion-icon>
          <input
            #campo
            type="text"
            role="combobox"
            aria-label="Buscar"
            aria-autocomplete="list"
            aria-controls="buscador-resultados"
            [attr.aria-expanded]="resultados().length > 0"
            [attr.aria-activedescendant]="resultados().length ? 'buscador-opcion-' + activo() : null"
            placeholder="Activo, servidor, IP, sensor, zona, intervención o alerta"
            autocomplete="off"
            spellcheck="false"
            [value]="consulta()"
            (input)="escribir($event)"
            (keydown)="teclaCampo($event)"
          />
          <button type="button" class="buscador__cerrar" (click)="cerrar()" aria-label="Cerrar el buscador"><kbd>Esc</kbd></button>
        </div>

        <div class="buscador__cuerpo">
          @if (indice() === null) {
            <p class="buscador__nota" aria-busy="true">Cargando…</p>
          } @else if (!consulta().trim()) {
            <p class="buscador__nota">
              Escribe un código, nombre, IP, rack o problema.<br />
              Usa ↑ ↓ para moverte y Enter para abrir.
            </p>
          } @else if (resultados().length === 0) {
            <p class="buscador__nota">
              @if (cargandoMas()) { Buscando… } @else { Sin resultados para «{{ consulta().trim() }}». }
            </p>
          } @else {
            <div id="buscador-resultados" role="listbox" aria-label="Resultados">
              @for (g of grupos(); track g.tipo; let n = $index) {
                <div role="group" [attr.aria-labelledby]="'buscador-grupo-' + n">
                  <p class="buscador__grupo" [id]="'buscador-grupo-' + n">
                    {{ g.tipo }}
                    @if (g.total > g.items.length) { <span>· {{ g.items.length }} de {{ g.total }}</span> }
                  </p>
                  @for (r of g.items; track r.clave) {
                    <div
                      role="option"
                      class="buscador__opcion"
                      [id]="'buscador-opcion-' + r.posicion"
                      [attr.aria-selected]="r.posicion === activo()"
                      [class.activa]="r.posicion === activo()"
                      (mousemove)="activo.set(r.posicion)"
                      (click)="abrir(r)"
                    >
                      <span class="opcion__titulo">{{ r.titulo }}</span>
                      <span class="opcion__detalle">{{ r.detalle }}</span>
                    </div>
                  }
                </div>
              }
            </div>
            @if (cargandoMas()) { <p class="buscador__mas">Consultando más fuentes…</p> }
          }
          <p class="oculto" aria-live="polite">
            @if (consulta().trim() && indice() !== null) { {{ resultados().length }} resultados }
          </p>
        </div>
      </div>
    }
  `,
  styles: `
    .fondo {
      position: fixed;
      inset: 0;
      z-index: 30000;
      background: rgba(15, 27, 36, 0.45);
    }
    .buscador {
      position: fixed;
      z-index: 30001;
      top: max(56px, 12vh);
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      flex-direction: column;
      width: min(640px, calc(100vw - 32px));
      max-height: min(70vh, 560px);
      overflow: hidden;
      border-radius: 12px;
      background: var(--sicma-superficie);
      box-shadow: 0 24px 60px rgba(15, 27, 36, 0.28);
    }
    .buscador__campo {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--sicma-linea);
    }
    .buscador__campo ion-icon {
      flex-shrink: 0;
      font-size: 1.15rem;
      color: var(--sicma-tenue);
    }
    input {
      flex: 1;
      min-width: 0;
      border: 0;
      outline: 0;
      background: transparent;
      color: var(--sicma-tinta);
      font: inherit;
      font-size: 1rem;
    }
    kbd {
      padding: 2px 6px;
      border: 1px solid var(--sicma-linea);
      border-radius: 4px;
      background: var(--sicma-fondo);
      color: var(--sicma-tenue);
      font-family: var(--sicma-mono);
      font-size: 0.7rem;
    }
    .buscador__cerrar {
      padding: 0;
      border: 0;
      background: none;
      cursor: pointer;
    }
    .buscador__cerrar:focus-visible {
      outline: 2px solid var(--ion-color-primary);
      outline-offset: 2px;
      border-radius: 4px;
    }
    .buscador__cuerpo {
      overflow-y: auto;
      padding: 4px 0 8px;
    }
    .buscador__nota {
      margin: 0;
      padding: 18px 16px;
      font-size: 0.85rem;
      line-height: 1.5;
      text-align: center;
      color: var(--sicma-tenue);
    }
    .buscador__mas {
      margin: 8px 16px 0;
      font-size: 0.75rem;
      color: var(--sicma-tenue);
    }
    .buscador__grupo {
      margin: 10px 16px 4px;
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      color: var(--sicma-tenue);
    }
    .buscador__grupo span {
      font-weight: 400;
      letter-spacing: 0;
      text-transform: none;
    }
    .buscador__opcion {
      display: flex;
      flex-direction: column;
      gap: 1px;
      margin: 0 6px;
      padding: 8px 10px;
      border-radius: 8px;
      cursor: pointer;
    }
    .buscador__opcion.activa {
      background: var(--sicma-primario-suave);
    }
    .opcion__titulo,
    .opcion__detalle {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .opcion__titulo {
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--sicma-tinta);
    }
    .opcion__detalle {
      font-size: 0.75rem;
      color: var(--sicma-tenue);
    }
    .oculto {
      position: absolute;
      width: 1px;
      height: 1px;
      margin: -1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }
    @media (max-width: 767px) {
      .buscador {
        top: 8px;
        max-height: calc(100vh - 16px);
      }
    }
  `,
})
export class BuscadorComponent {
  protected readonly servicio = inject(BuscadorService);
  private readonly router = inject(Router);

  protected readonly consulta = signal('');
  /** Todo lo que se puede encontrar; null hasta que llega la primera fuente. */
  protected readonly indice = signal<ElementoBusqueda[] | null>(null);
  /** Aún faltan fuentes por responder (p. ej. Zabbix lento): se avisa bajo los resultados. */
  protected readonly cargandoMas = signal(false);
  private carga: Subscription | null = null;
  /** Posición del resultado elegido con las flechas o el puntero. */
  protected readonly activo = signal(0);
  private readonly campo = viewChild<ElementRef<HTMLInputElement>>('campo');
  /** Dónde estaba el foco al abrir, para devolverlo al cerrar. */
  private focoPrevio: HTMLElement | null = null;

  /** Coinciden los que contienen todas las palabras; primero los que empiezan con lo escrito. */
  protected readonly grupos = computed(() => {
    const palabras = normalizar(this.consulta()).split(/\s+/).filter(Boolean);
    const indice = this.indice();
    if (palabras.length === 0 || !indice) {
      return [];
    }
    const frase = palabras.join(' ');
    const peso = (e: ElementoBusqueda) =>
      e.tituloNormalizado.startsWith(frase) ? 0 : e.tituloNormalizado.includes(frase) ? 1 : 2;
    const coincidencias = indice.filter((e) => palabras.every((p) => e.texto.includes(p)));
    let posicion = 0;
    return TIPOS_BUSQUEDA.map((tipo) => {
      const delTipo = coincidencias.filter((e) => e.tipo === tipo).sort((a, b) => peso(a) - peso(b));
      const items: Resultado[] = delTipo.slice(0, POR_GRUPO).map((e) => ({ ...e, posicion: posicion++ }));
      return { tipo, total: delTipo.length, items };
    }).filter((g) => g.items.length > 0);
  });

  protected readonly resultados = computed(() => this.grupos().flatMap((g) => g.items));

  constructor() {
    addIcons({ searchOutline });

    effect(() => {
      if (this.servicio.abierto()) {
        untracked(() => this.preparar());
      }
    });
    // Al cerrar sesión se cierra y se olvidan los resultados.
    effect(() => {
      if (!this.servicio.disponible()) {
        untracked(() => {
          this.servicio.cerrar();
          this.indice.set(null);
        });
      }
    });
    effect(() => this.campo()?.nativeElement.focus());
  }

  /** Ctrl K / ⌘ K abre o cierra el buscador desde cualquier pantalla; Esc lo cierra. */
  protected atajo(evento: KeyboardEvent): void {
    if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === 'k') {
      if (!this.servicio.disponible()) {
        return;
      }
      evento.preventDefault();
      if (this.servicio.abierto()) {
        this.cerrar();
      } else {
        this.servicio.abrir();
      }
    } else if (evento.key === 'Escape' && this.servicio.abierto()) {
      evento.preventDefault();
      this.cerrar();
    }
  }

  protected escribir(evento: Event): void {
    this.consulta.set((evento.target as HTMLInputElement).value);
    this.activo.set(0);
  }

  protected teclaCampo(evento: KeyboardEvent): void {
    const total = this.resultados().length;
    switch (evento.key) {
      case 'ArrowDown':
        if (total) {
          this.moverA((this.activo() + 1) % total);
        }
        break;
      case 'ArrowUp':
        if (total) {
          this.moverA((this.activo() - 1 + total) % total);
        }
        break;
      case 'Enter': {
        const elegido = this.resultados()[this.activo()];
        if (elegido) {
          this.abrir(elegido);
        }
        break;
      }
      case 'Tab':
        break; // el foco se queda en el campo mientras el buscador está abierto
      default:
        return;
    }
    evento.preventDefault();
  }

  protected abrir(resultado: ElementoBusqueda): void {
    this.cerrar(false);
    void this.router.navigate(resultado.ruta, { queryParams: resultado.queryParams });
  }

  protected cerrar(devolverFoco = true): void {
    this.carga?.unsubscribe();
    this.carga = null;
    this.servicio.cerrar();
    if (devolverFoco) {
      this.focoPrevio?.focus?.();
    }
    this.focoPrevio = null;
  }

  private preparar(): void {
    this.focoPrevio = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    this.consulta.set('');
    this.activo.set(0);
    this.indice.set(null);
    this.cargandoMas.set(true);
    this.carga?.unsubscribe();
    this.carga = this.servicio.indice().subscribe({
      next: (elementos) => this.indice.set(elementos),
      error: () => {
        this.indice.update((actual) => actual ?? []);
        this.cargandoMas.set(false);
      },
      complete: () => {
        this.indice.update((actual) => actual ?? []);
        this.cargandoMas.set(false);
      },
    });
  }

  private moverA(posicion: number): void {
    this.activo.set(posicion);
    queueMicrotask(() => document.getElementById(`buscador-opcion-${posicion}`)?.scrollIntoView({ block: 'nearest' }));
  }
}
