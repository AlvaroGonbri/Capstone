import {
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { Subscription } from 'rxjs';
import { HistorialSensor, PuntoHistorial, RangoHistorial } from '../core/models';
import { MonitoreoService } from '../core/services/monitoreo.service';

/** Sensor que se puede graficar. */
export interface SensorGrafico {
  id: number;
  codigo: string;
  ubicacion: string;
}

type Variable = 'temperatura' | 'humedad';

const VARIABLES: Variable[] = ['temperatura', 'humedad'];

const RANGOS: { valor: RangoHistorial; etiqueta: string; texto: string }[] = [
  { valor: '24h', etiqueta: '24 h', texto: 'las últimas 24 horas' },
  { valor: '7d', etiqueta: '7 d', texto: 'los últimos 7 días' },
  { valor: '30d', etiqueta: '30 d', texto: 'los últimos 30 días' },
];

const SERIES: Record<Variable, { titulo: string; unidad: string; eje: string; minimoVisible: number }> = {
  temperatura: { titulo: 'Temperatura', unidad: '°C', eje: '°', minimoVisible: 4 },
  humedad: { titulo: 'Humedad', unidad: '%', eje: '%', minimoVisible: 10 },
};

const EXTREMOS: Record<Variable, readonly [keyof PuntoHistorial, keyof PuntoHistorial]> = {
  temperatura: ['temperaturaMin', 'temperaturaMax'],
  humedad: ['humedadMin', 'humedadMax'],
};

/** Márgenes del dibujo, en píxeles: ejes a la izquierda, último valor a la derecha. */
const MARGEN = { izq: 40, der: 50, arriba: 24, separacion: 36, eje: 26 };
/** Distancia máxima del puntero a un tramo para mostrar su lectura. */
const ALCANCE_PUNTERO = 40;
/** El gráfico se actualiza solo cada minuto, sin atenuarse (con la pestaña oculta no consulta). */
const REFRESCO_MS = 60_000;

const numero = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1 });
const dos = (n: number) => String(n).padStart(2, '0');
const diaMes = (d: Date) => `${dos(d.getDate())}/${dos(d.getMonth() + 1)}`;
const horaMinuto = (d: Date) => `${dos(d.getHours())}:${dos(d.getMinutes())}`;

interface Panel {
  variable: Variable;
  titulo: string;
  unidad: string;
  arriba: number;
  alto: number;
  ticks: { y: number; texto: string }[];
  banda: { y: number; alto: number; texto: string } | null;
  trazos: string[];
  aislados: { x: number; y: number }[];
  final: { x: number; y: number; texto: string } | null;
  y: (valor: number) => number;
}

interface Geometria {
  ancho: number;
  alto: number;
  x0: number;
  x1: number;
  paneles: Panel[];
  huecos: { x: number; ancho: number }[];
  marcasX: { x: number; texto: string }[];
  /** Centro horizontal de cada tramo, en el mismo orden que los puntos. */
  xs: number[];
}

/** Escala con valores redondos (paso 1, 2, 2,5 o 5 × 10ⁿ) que incluye todos los valores. */
function escala(valores: number[], minimoVisible: number): { min: number; max: number; ticks: number[] } {
  let bajo = Math.min(...valores);
  let alto = Math.max(...valores);
  if (alto - bajo < minimoVisible) {
    const centro = (alto + bajo) / 2;
    bajo = centro - minimoVisible / 2;
    alto = centro + minimoVisible / 2;
  }
  const bruto = (alto - bajo) / 3;
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= bruto) ?? 10 * potencia;
  const min = Math.floor(bajo / paso) * paso;
  const max = Math.ceil(alto / paso) * paso;
  const ticks: number[] = [];
  for (let v = min; v <= max + paso / 1000; v += paso) {
    ticks.push(Number(v.toFixed(6)));
  }
  return { min, max, ticks };
}

/** Marcas del eje de tiempo en hora local: cada 3 h (24 h), cada día (7 d) o cada 5 días (30 d). */
function marcasTiempo(desde: number, hasta: number, rango: RangoHistorial, angosto: boolean): { t: number; texto: string }[] {
  const marcas: { t: number; texto: string }[] = [];
  const d = new Date(desde);
  if (rango === '24h') {
    const cada = angosto ? 6 : 3;
    d.setMinutes(0, 0, 0);
    d.setHours(d.getHours() + 1);
    while (d.getHours() % cada !== 0) {
      d.setHours(d.getHours() + 1);
    }
    for (; d.getTime() <= hasta; d.setHours(d.getHours() + cada)) {
      marcas.push({ t: d.getTime(), texto: horaMinuto(d) });
    }
  } else {
    const cada = rango === '7d' ? (angosto ? 2 : 1) : angosto ? 10 : 5;
    d.setHours(24, 0, 0, 0); // la medianoche siguiente
    for (; d.getTime() <= hasta; d.setDate(d.getDate() + cada)) {
      marcas.push({ t: d.getTime(), texto: diaMes(d) });
    }
  }
  return marcas;
}

/** "14/11 09:10–09:20", o con las dos fechas si el tramo cruza la medianoche. */
function textoTramo(punto: PuntoHistorial, pasoSegundos: number): string {
  const inicio = new Date(punto.fecha);
  const fin = new Date(inicio.getTime() + pasoSegundos * 1000);
  return inicio.toDateString() === fin.toDateString() || (fin.getHours() === 0 && fin.getMinutes() === 0)
    ? `${diaMes(inicio)} ${horaMinuto(inicio)}–${horaMinuto(fin)}`
    : `${diaMes(inicio)} ${horaMinuto(inicio)} – ${diaMes(fin)} ${horaMinuto(fin)}`;
}

function textoPaso(segundos: number): string {
  return segundos < 3600 ? `${Math.round(segundos / 60)} min` : `${Math.round(segundos / 3600)} h`;
}

/**
 * Gráfico de temperatura y humedad de un sensor (24 h / 7 d / 30 d).
 *
 * Son dos paneles con el mismo eje de tiempo, uno por variable, en vez de dos escalas en un mismo
 * gráfico: así no se insinúa una relación entre °C y % que no existe. Cada panel muestra su rango
 * permitido como banda; los períodos sin lecturas se ven como "Sin datos" (la línea no los une).
 */
@Component({
  selector: 'app-grafico-ambiental',
  templateUrl: './grafico-ambiental.component.html',
  styleUrl: './grafico-ambiental.component.scss',
})
export class GraficoAmbientalComponent {
  private readonly servicio = inject(MonitoreoService);

  /** Sensores que se pueden graficar; al abrir se muestra el primero. */
  readonly sensores = input.required<SensorGrafico[]>();
  readonly titulo = input('Temperatura y humedad');
  readonly rangoInicial = input<RangoHistorial>('24h');

  protected readonly rangos = RANGOS;
  protected readonly textoPaso = textoPaso;
  protected readonly rango = linkedSignal(() => this.rangoInicial());
  /** El sensor elegido se mantiene aunque la lista se recargue, mientras siga en ella. */
  protected readonly elegido = linkedSignal<SensorGrafico[], number | null>({
    source: this.sensores,
    computation: (lista, previo) =>
      previo?.value != null && lista.some((s) => s.id === previo.value) ? previo.value : (lista[0]?.id ?? null),
  });
  protected readonly sensorElegido = computed(() => this.sensores().find((s) => s.id === this.elegido()) ?? null);

  protected readonly datos = signal<HistorialSensor | null>(null);
  protected readonly cargando = signal(false);
  protected readonly error = signal(false);
  /** Tramo bajo el puntero (o elegido con las flechas); null = ninguno. */
  protected readonly activo = signal<number | null>(null);
  private readonly ancho = signal(0);

  private readonly lienzo = viewChild.required<ElementRef<HTMLElement>>('lienzo');
  private peticion: Subscription | null = null;

  protected readonly geometria = computed<Geometria | null>(() => {
    const datos = this.datos();
    const ancho = this.ancho();
    if (!datos || datos.puntos.length === 0 || ancho < 200) {
      return null;
    }
    const altoPanel = ancho < 480 ? 96 : 128;
    const desde = Date.parse(datos.desde);
    const hasta = Date.parse(datos.hasta);
    const paso = datos.pasoSegundos * 1000;
    const x0 = MARGEN.izq;
    const x1 = ancho - MARGEN.der;
    const x = (t: number) => x0 + ((t - desde) / (hasta - desde)) * (x1 - x0);

    const inicios = datos.puntos.map((p) => Date.parse(p.fecha));
    const xs = inicios.map((t) => x(Math.min(t + paso / 2, hasta)));

    // Más de un tramo seguido sin lecturas es "sin datos": se sombrea y la línea se corta ahí.
    const huecos: Geometria['huecos'] = [];
    const cortes = inicios.map((t, i) => i > 0 && t - (inicios[i - 1] + paso) > paso);
    const agregarHueco = (inicio: number, fin: number) => {
      if (fin - inicio > paso) {
        huecos.push({ x: x(inicio), ancho: x(fin) - x(inicio) });
      }
    };
    let cubierto = desde;
    for (const t of inicios) {
      agregarHueco(cubierto, t);
      cubierto = t + paso;
    }
    agregarHueco(cubierto, hasta);

    const paneles = VARIABLES.map((variable, n): Panel => {
      const serie = SERIES[variable];
      const arriba = MARGEN.arriba + n * (altoPanel + MARGEN.separacion);
      const valores = datos.puntos.map((p) => p[variable]);
      const umbral = datos.umbrales[variable];
      const conocidos = valores.filter((v): v is number => v !== null);
      const limites = umbral ? [umbral.minimo, umbral.maximo] : [];
      const { min, max, ticks } = escala(conocidos.length || limites.length ? [...conocidos, ...limites] : [0], serie.minimoVisible);
      const y = (v: number) => arriba + altoPanel - ((v - min) / (max - min)) * altoPanel;

      const trazos: string[] = [];
      const aislados: Panel['aislados'] = [];
      let tramo: { x: number; y: number }[] = [];
      const cerrar = () => {
        if (tramo.length === 1) {
          aislados.push(tramo[0]);
        } else if (tramo.length > 1) {
          trazos.push('M' + tramo.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join('L'));
        }
        tramo = [];
      };
      valores.forEach((v, i) => {
        if (cortes[i]) {
          cerrar();
        }
        if (v === null) {
          cerrar();
          return;
        }
        tramo.push({ x: xs[i], y: y(v) });
      });
      cerrar();

      let ultimo = -1;
      valores.forEach((v, i) => {
        if (v !== null) {
          ultimo = i;
        }
      });

      return {
        variable,
        titulo: serie.titulo,
        unidad: serie.unidad,
        arriba,
        alto: altoPanel,
        ticks: ticks.map((v) => ({ y: y(v), texto: `${numero.format(v)}${serie.eje}` })),
        banda: umbral
          ? {
              y: y(umbral.maximo),
              alto: y(umbral.minimo) - y(umbral.maximo),
              texto: `rango ${numero.format(umbral.minimo)}–${numero.format(umbral.maximo)} ${serie.unidad}`,
            }
          : null,
        trazos,
        aislados,
        final:
          ultimo >= 0
            ? { x: xs[ultimo], y: y(valores[ultimo]!), texto: `${numero.format(valores[ultimo]!)}${serie.eje}` }
            : null,
        y,
      };
    });

    return {
      ancho,
      alto: MARGEN.arriba + 2 * altoPanel + MARGEN.separacion + MARGEN.eje,
      x0,
      x1,
      paneles,
      huecos,
      marcasX: marcasTiempo(desde, hasta, datos.rango, x1 - x0 < 420)
        .map((m) => ({ x: x(m.t), texto: m.texto }))
        .filter((m) => m.x >= x0 && m.x <= x1),
      xs,
    };
  });

  /** Lectura del tramo activo: línea vertical, puntos en ambas series y el recuadro con valores. */
  protected readonly lectura = computed(() => {
    const i = this.activo();
    const datos = this.datos();
    const g = this.geometria();
    if (i === null || !datos || !g || i >= datos.puntos.length) {
      return null;
    }
    const punto = datos.puntos[i];
    const valores = g.paneles.flatMap((panel) => {
      const valor = punto[panel.variable];
      if (valor === null) {
        return [];
      }
      const [claveMin, claveMax] = EXTREMOS[panel.variable];
      const min = punto[claveMin] as number | null;
      const max = punto[claveMax] as number | null;
      return [
        {
          variable: panel.variable,
          titulo: panel.titulo,
          valor: `${numero.format(valor)} ${panel.unidad}`,
          extremos: min !== null && max !== null && min !== max ? `${numero.format(min)}–${numero.format(max)}` : '',
          y: panel.y(valor),
        },
      ];
    });
    return {
      x: g.xs[i],
      izquierda: g.xs[i] > g.ancho * 0.6,
      tramo: textoTramo(punto, datos.pasoSegundos),
      lecturas: punto.lecturas,
      valores,
    };
  });

  /** Lo que dice el gráfico, para lectores de pantalla (el detalle está en la tabla). */
  protected readonly resumen = computed(() => {
    const d = this.datos();
    if (!d || d.puntos.length === 0) {
      return '';
    }
    const partes = VARIABLES.flatMap((v) => {
      const valores = d.puntos.map((p) => p[v]).filter((x): x is number => x !== null);
      return valores.length
        ? [`${SERIES[v].titulo.toLowerCase()} promedio entre ${numero.format(Math.min(...valores))} y ${numero.format(Math.max(...valores))} ${SERIES[v].unidad}`]
        : [];
    });
    const periodo = RANGOS.find((r) => r.valor === d.rango)?.texto ?? '';
    return `${d.codigo}, ${periodo}: ${partes.join('; ')}. Usa las flechas para recorrer los tramos.`;
  });

  /** Tabla equivalente al gráfico, del tramo más reciente al más antiguo. */
  protected readonly filas = computed(() => {
    const d = this.datos();
    if (!d) {
      return [];
    }
    const valor = (p: PuntoHistorial, v: Variable) => {
      const promedio = p[v];
      if (promedio === null) {
        return '—';
      }
      const [claveMin, claveMax] = EXTREMOS[v];
      const min = p[claveMin] as number | null;
      const max = p[claveMax] as number | null;
      return min !== null && max !== null && min !== max
        ? `${numero.format(promedio)} (${numero.format(min)}–${numero.format(max)})`
        : numero.format(promedio);
    };
    return [...d.puntos].reverse().map((p) => ({
      fecha: p.fecha,
      tramo: textoTramo(p, d.pasoSegundos),
      temperatura: valor(p, 'temperatura'),
      humedad: valor(p, 'humedad'),
      lecturas: p.lecturas,
    }));
  });

  protected readonly textoRango = (rango: RangoHistorial) => RANGOS.find((r) => r.valor === rango)?.texto ?? '';

  constructor() {
    effect(() => {
      const id = this.elegido();
      const rango = this.rango();
      untracked(() => this.cargar(id, rango));
    });

    const temporizador = setInterval(() => {
      if (!document.hidden) {
        this.cargar(this.elegido(), this.rango(), true);
      }
    }, REFRESCO_MS);

    let observador: ResizeObserver | null = null;
    afterNextRender(() => {
      observador = new ResizeObserver(([entrada]) => this.ancho.set(Math.floor(entrada.contentRect.width)));
      observador.observe(this.lienzo().nativeElement);
    });

    inject(DestroyRef).onDestroy(() => {
      clearInterval(temporizador);
      observador?.disconnect();
      this.peticion?.unsubscribe();
    });
  }

  protected elegir(evento: Event): void {
    this.elegido.set(Number((evento.target as HTMLSelectElement).value));
  }

  protected reintentar(): void {
    this.cargar(this.elegido(), this.rango());
  }

  protected mover(evento: PointerEvent): void {
    const g = this.geometria();
    if (!g) {
      return;
    }
    const caja = (evento.currentTarget as Element).getBoundingClientRect();
    const px = evento.clientX - caja.left;
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

  /** Con el foco en el gráfico: ← → recorren los tramos, Inicio/Fin van a los extremos, Esc oculta. */
  protected tecla(evento: KeyboardEvent): void {
    const total = this.datos()?.puntos.length ?? 0;
    if (!total) {
      return;
    }
    const actual = this.activo();
    switch (evento.key) {
      case 'ArrowLeft':
        this.activo.set(Math.max(0, (actual ?? total) - 1));
        break;
      case 'ArrowRight':
        this.activo.set(Math.min(total - 1, (actual ?? -1) + 1));
        break;
      case 'Home':
        this.activo.set(0);
        break;
      case 'End':
        this.activo.set(total - 1);
        break;
      case 'Escape':
        this.activo.set(null);
        break;
      default:
        return;
    }
    evento.preventDefault();
  }

  protected enfocar(): void {
    const total = this.datos()?.puntos.length ?? 0;
    if (this.activo() === null && total) {
      this.activo.set(total - 1);
    }
  }

  /** Al cambiar de sensor o de período el gráfico anterior queda atenuado hasta que llegan los datos. */
  private cargar(id: number | null, rango: RangoHistorial, silencioso = false): void {
    if (id === null) {
      this.datos.set(null);
      return;
    }
    this.peticion?.unsubscribe();
    if (!silencioso) {
      this.cargando.set(true);
    }
    this.peticion = this.servicio.historialSensor(id, rango).subscribe({
      next: (datos) => {
        this.datos.set(datos);
        this.error.set(false);
        this.cargando.set(false);
        if ((this.activo() ?? 0) >= datos.puntos.length) {
          this.activo.set(null);
        }
      },
      error: () => {
        if (!silencioso) {
          this.error.set(true);
        }
        this.cargando.set(false);
      },
    });
  }
}
