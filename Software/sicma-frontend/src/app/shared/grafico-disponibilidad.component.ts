import {
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';

/** Un día del período con su disponibilidad promedio (null = Zabbix no tiene datos de ese día). */
export interface PuntoDisponibilidad {
  fecha: string;
  porcentaje: number | null;
}

const ALTO = 190;
const MARGEN = { izq: 44, der: 58, arr: 12, aba: 26 };
const ALCANCE_PUNTERO = 40;

const porcentaje = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 2 });

function textoDia(iso: string, conAnio = false): string {
  const [a, m, d] = iso.split('-');
  return conAnio ? `${d}-${m}-${a}` : `${d}-${m}`;
}

/** Eje Y: hasta 100 % y desde un múltiplo de 5 bajo el mínimo (una línea no necesita partir en cero). */
function escalaY(valores: number[]): { min: number; ticks: number[] } {
  const bajo = Math.min(...valores, 99);
  const min = Math.max(0, Math.floor((bajo - 0.001) / 5) * 5);
  const paso = 100 - min <= 25 ? 5 : 100 - min <= 50 ? 10 : 20;
  const ticks: number[] = [];
  for (let v = min; v <= 100; v += paso) ticks.push(v);
  return { min, ticks };
}

/**
 * Disponibilidad diaria de los servidores en el período (Reportes). Una sola serie: el título la nombra
 * y no lleva leyenda. Los días sin datos cortan la línea; puntero o ← → muestran el valor de cada día.
 */
@Component({
  selector: 'app-grafico-disponibilidad',
  template: `
    <div class="lienzo" #lienzo>
      @if (geometria(); as g) {
        <svg
          [attr.viewBox]="'0 0 ' + g.ancho + ' ' + alto"
          [attr.width]="g.ancho"
          [attr.height]="alto"
          role="img"
          tabindex="0"
          [attr.aria-label]="resumen()"
          (pointermove)="mover($event)"
          (pointerleave)="activo.set(null)"
          (keydown)="tecla($event)"
          (blur)="activo.set(null)"
        >
          @for (t of g.ticksY; track t.v) {
            <line class="grilla" [attr.x1]="margen.izq" [attr.x2]="g.ancho - margen.der" [attr.y1]="t.y" [attr.y2]="t.y" />
            <text class="eje" [attr.x]="margen.izq - 8" [attr.y]="t.y + 4" text-anchor="end">{{ t.v }} %</text>
          }
          @for (t of g.ticksX; track t.i) {
            <text class="eje" [attr.x]="t.x" [attr.y]="alto - 6" text-anchor="middle">{{ t.texto }}</text>
          }
          @for (tramo of g.tramos; track $index) {
            @if (tramo.length > 1) {
              <polyline class="linea" [attr.points]="tramo.join(' ')" />
            } @else {
              <circle class="punto-suelto" [attr.cx]="tramo[0].split(',')[0]" [attr.cy]="tramo[0].split(',')[1]" r="2.5" />
            }
          }
          @if (g.final; as f) {
            <circle class="final" [attr.cx]="f.x" [attr.cy]="f.y" r="4" />
            <text class="valor-final" [attr.x]="f.x + 8" [attr.y]="f.y + 4">{{ formato(f.v) }} %</text>
          }
          @if (lectura(); as l) {
            <line class="guia" [attr.x1]="l.x" [attr.x2]="l.x" [attr.y1]="margen.arr" [attr.y2]="alto - margen.aba" />
            @if (l.y !== null) {
              <circle class="final" [attr.cx]="l.x" [attr.cy]="l.y" r="4" />
            }
          }
        </svg>
        @if (lectura(); as l) {
          <div class="tooltip" [style.left.px]="l.x" role="status">
            <strong>{{ l.valor }}</strong>
            <span>{{ l.fecha }}</span>
          </div>
        }
      } @else {
        <p class="vacio">Sin datos de disponibilidad en el período.</p>
      }
    </div>
    @if (puntos().length) {
      <details class="tabla-datos">
        <summary>Ver como tabla</summary>
        <table>
          <thead><tr><th scope="col">Día</th><th scope="col">Disponibilidad</th></tr></thead>
          <tbody>
            @for (p of puntos(); track p.fecha) {
              <tr><td>{{ dia(p.fecha) }}</td><td>{{ p.porcentaje === null ? 'Sin datos' : formato(p.porcentaje) + ' %' }}</td></tr>
            }
          </tbody>
        </table>
      </details>
    }
  `,
  styles: `
    :host { display: block; }
    .lienzo { position: relative; width: 100%; min-height: 60px; }
    svg { display: block; outline: none; touch-action: pan-y; }
    svg:focus-visible { outline: 2px solid var(--ion-color-primary); outline-offset: 2px; border-radius: 4px; }
    .grilla { stroke: var(--sicma-linea-suave); stroke-width: 1; }
    .eje { fill: var(--sicma-tenue); font-size: 11px; font-family: var(--sicma-mono); }
    .linea { fill: none; stroke: var(--ion-color-primary); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
    .punto-suelto { fill: var(--ion-color-primary); }
    .final { fill: var(--ion-color-primary); stroke: var(--sicma-superficie); stroke-width: 2; }
    .valor-final { fill: var(--sicma-tinta); font-size: 12px; font-weight: 600; }
    .guia { stroke: var(--sicma-tenue); stroke-width: 1; stroke-dasharray: 3 3; }
    .tooltip {
      position: absolute; top: 4px; transform: translateX(-50%); pointer-events: none;
      display: flex; flex-direction: column; gap: 1px; padding: 6px 9px; border-radius: 7px;
      background: var(--sicma-tinta); color: #fff; font-size: 0.75rem; white-space: nowrap;
      box-shadow: 0 6px 18px -8px rgba(0, 0, 0, 0.45);
    }
    .tooltip strong { font-size: 0.85rem; }
    .tooltip span { color: #c8d3da; }
    .vacio { margin: 18px 0; font-size: 0.82rem; color: var(--sicma-tenue); text-align: center; }
    .tabla-datos { margin-top: 6px; font-size: 0.8rem; color: var(--sicma-tinta-2); }
    .tabla-datos summary { cursor: pointer; color: var(--ion-color-primary); }
    .tabla-datos table { margin-top: 6px; border-collapse: collapse; }
    .tabla-datos th, .tabla-datos td { padding: 3px 14px 3px 0; text-align: left; border-bottom: 1px solid var(--sicma-linea-suave); }
    .tabla-datos th { font-weight: 600; color: var(--sicma-tenue); }
  `,
})
export class GraficoDisponibilidadComponent {
  readonly puntos = input.required<PuntoDisponibilidad[]>();

  protected readonly alto = ALTO;
  protected readonly margen = MARGEN;
  protected readonly activo = signal<number | null>(null);
  private readonly ancho = signal(0);
  private readonly lienzo = viewChild.required<ElementRef<HTMLElement>>('lienzo');

  protected readonly geometria = computed(() => {
    const puntos = this.puntos();
    const ancho = this.ancho();
    const valores = puntos.map((p) => p.porcentaje).filter((v): v is number => v !== null);
    if (!valores.length || ancho < 120) return null;

    const { min, ticks } = escalaY(valores);
    const n = puntos.length;
    const util = ancho - MARGEN.izq - MARGEN.der;
    const x = (i: number) => MARGEN.izq + (n === 1 ? util / 2 : (util * i) / (n - 1));
    const y = (v: number) => MARGEN.arr + (ALTO - MARGEN.arr - MARGEN.aba) * (1 - (v - min) / (100 - min));

    const tramos: string[][] = [];
    let actual: string[] = [];
    puntos.forEach((p, i) => {
      if (p.porcentaje === null) {
        if (actual.length) tramos.push(actual);
        actual = [];
      } else {
        actual.push(`${x(i).toFixed(1)},${y(p.porcentaje).toFixed(1)}`);
      }
    });
    if (actual.length) tramos.push(actual);

    let ultimo = -1;
    puntos.forEach((p, i) => p.porcentaje !== null && (ultimo = i));
    const cuantas = Math.min(n, ancho < 480 ? 4 : 6);
    const indices = cuantas <= 1 ? [0] : Array.from({ length: cuantas }, (_, k) => Math.round((k * (n - 1)) / (cuantas - 1)));

    return {
      ancho,
      xs: puntos.map((_, i) => x(i)),
      y,
      tramos,
      ticksY: ticks.map((v) => ({ v, y: y(v) })),
      ticksX: [...new Set(indices)].map((i) => ({ i, x: x(i), texto: textoDia(puntos[i].fecha) })),
      final: ultimo >= 0 ? { x: x(ultimo), y: y(puntos[ultimo].porcentaje!), v: puntos[ultimo].porcentaje! } : null,
    };
  });

  /** Lo que muestra la guía: el valor primero, luego el día. */
  protected readonly lectura = computed(() => {
    const i = this.activo();
    const g = this.geometria();
    if (i === null || !g) return null;
    const p = this.puntos()[i];
    return {
      x: g.xs[i],
      y: p.porcentaje === null ? null : g.y(p.porcentaje),
      valor: p.porcentaje === null ? 'Sin datos' : `${this.formato(p.porcentaje)} %`,
      fecha: textoDia(p.fecha, true),
    };
  });

  protected readonly resumen = computed(() => {
    const con = this.puntos().filter((p) => p.porcentaje !== null) as { fecha: string; porcentaje: number }[];
    if (!con.length) return 'Sin datos de disponibilidad en el período.';
    const peor = con.reduce((a, b) => (b.porcentaje < a.porcentaje ? b : a));
    const promedio = con.reduce((s, p) => s + p.porcentaje, 0) / con.length;
    return (
      `Disponibilidad diaria de los servidores: promedio ${this.formato(promedio)} %, ` +
      `mínimo ${this.formato(peor.porcentaje)} % el ${textoDia(peor.fecha, true)}. Use las flechas para recorrer los días.`
    );
  });

  constructor() {
    let observador: ResizeObserver | null = null;
    afterNextRender(() => {
      observador = new ResizeObserver(([entrada]) => this.ancho.set(Math.floor(entrada.contentRect.width)));
      observador.observe(this.lienzo().nativeElement);
    });
    inject(DestroyRef).onDestroy(() => observador?.disconnect());
  }

  protected formato(v: number): string {
    return porcentaje.format(v);
  }

  protected dia(iso: string): string {
    return textoDia(iso, true);
  }

  protected mover(evento: PointerEvent): void {
    const g = this.geometria();
    if (!g) return;
    const px = evento.clientX - (evento.currentTarget as Element).getBoundingClientRect().left;
    let mejor = -1;
    let distancia = Infinity;
    g.xs.forEach((x, i) => {
      const d = Math.abs(x - px);
      if (d < distancia) {
        distancia = d;
        mejor = i;
      }
    });
    this.activo.set(distancia <= ALCANCE_PUNTERO ? mejor : null);
  }

  protected tecla(evento: KeyboardEvent): void {
    const total = this.puntos().length;
    if (!total) return;
    const actual = this.activo();
    const siguiente: Record<string, number | null> = {
      ArrowLeft: Math.max(0, (actual ?? total) - 1),
      ArrowRight: Math.min(total - 1, (actual ?? -1) + 1),
      Home: 0,
      End: total - 1,
      Escape: null,
    };
    if (evento.key in siguiente) {
      evento.preventDefault();
      this.activo.set(siguiente[evento.key]);
    }
  }
}
