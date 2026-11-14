import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, catchError, forkJoin, map, merge, of, shareReplay, tap } from 'rxjs';
import { Activo, ActivoInventario, Alerta, EstadoSensor, Intervencion, UbicacionCatalogo } from '../models';
import { ActivosService } from './activos.service';
import { AuthService } from './auth.service';
import { CatalogosService } from './catalogos.service';
import { IntervencionesService, etiquetaEstadoIntervencion, tituloIntervencion } from './intervenciones.service';
import { InventarioService } from './inventario.service';
import { MonitoreoService } from './monitoreo.service';

/** Grupos de resultados, en el orden en que se muestran. */
export const TIPOS_BUSQUEDA = ['Activos', 'Servidores', 'Sensores', 'Zonas', 'Intervenciones', 'Alertas'] as const;
export type TipoBusqueda = (typeof TIPOS_BUSQUEDA)[number];

export interface ElementoBusqueda {
  clave: string;
  tipo: TipoBusqueda;
  titulo: string;
  detalle: string;
  ruta: (string | number)[];
  queryParams?: Record<string, string | number>;
  /** Texto normalizado (sin tildes, en minúsculas) donde se busca. */
  texto: string;
  /** Título normalizado, para ordenar primero lo que empieza con lo escrito. */
  tituloNormalizado: string;
}

/** Los datos se reutilizan durante un minuto entre una búsqueda y otra. */
const VIGENCIA_MS = 60_000;

/** Sin tildes y en minúsculas: "Ubicación" coincide con "ubicacion". */
export function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function elemento(
  datos: Omit<ElementoBusqueda, 'texto' | 'tituloNormalizado'>,
  ...extras: Array<string | null | undefined>
): ElementoBusqueda {
  return {
    ...datos,
    texto: normalizar([datos.titulo, datos.detalle, ...extras].filter(Boolean).join(' ')),
    tituloNormalizado: normalizar(datos.titulo),
  };
}

/**
 * Buscador global (Ctrl K): activos, servidores de Zabbix, sensores, zonas, intervenciones y
 * alertas abiertas. Usa los mismos endpoints que las pantallas, así cada rol encuentra solo lo
 * que ya puede ver (p. ej. el técnico, solo sus intervenciones). No busca en accesos ni personal.
 */
@Injectable({ providedIn: 'root' })
export class BuscadorService {
  private readonly auth = inject(AuthService);
  private readonly inventario = inject(InventarioService);
  private readonly zabbix = inject(ActivosService);
  private readonly monitoreo = inject(MonitoreoService);
  private readonly catalogos = inject(CatalogosService);
  private readonly intervenciones = inject(IntervencionesService);

  readonly abierto = signal(false);
  /** Contratistas solo ven Personal externo: para ellos no hay buscador. */
  readonly disponible = computed(() => this.auth.autenticado() && !this.auth.tieneRol('contratistas'));

  /** Va asociado al usuario: tras cambiar de sesión no se muestran datos de la cuenta anterior. */
  private cache: { usuario: number | undefined; hasta: number; elementos: ElementoBusqueda[] } | null = null;

  abrir(): void {
    if (this.disponible()) {
      this.abierto.set(true);
    }
  }

  cerrar(): void {
    this.abierto.set(false);
  }

  /**
   * Todo lo que se puede encontrar. Emite cada vez que llega una fuente (lo acumulado hasta ahí),
   * así una fuente lenta —p. ej. Zabbix caído— no retrasa el resto. Si una fuente falla, se omite.
   */
  indice(): Observable<ElementoBusqueda[]> {
    const usuario = this.auth.usuario()?.id;
    if (this.cache && this.cache.usuario === usuario && this.cache.hasta > Date.now()) {
      return of(this.cache.elementos);
    }
    const o = <T>(fuente: Observable<T[]>) => fuente.pipe(catchError(() => of([] as T[])));
    // El inventario se comparte: con él se sabe qué servidores y alertas tienen ficha.
    const activos$ = o(this.inventario.listar()).pipe(shareReplay(1));
    const fuentes: Observable<ElementoBusqueda[]>[] = [
      activos$.pipe(map((activos) => this.deActivos(activos))),
      forkJoin([o(this.zabbix.listar()), activos$]).pipe(map(([hosts, activos]) => this.deHosts(hosts, activos))),
      o(this.monitoreo.estadoSensores()).pipe(map((sensores) => this.deSensores(sensores))),
      o(this.catalogos.ubicaciones()).pipe(map((zonas) => this.deZonas(zonas))),
      o(this.intervenciones.listar()).pipe(map((lista) => this.deIntervenciones(lista))),
      forkJoin([o(this.zabbix.alertasAbiertas()), activos$]).pipe(map(([alertas, activos]) => this.deAlertas(alertas, activos))),
      o(this.monitoreo.alertasAbiertas()).pipe(map((alertas) => this.deAlertas(alertas, []))),
    ];
    let acumulados: ElementoBusqueda[] = [];
    return merge(...fuentes).pipe(
      map((nuevos) => (acumulados = [...acumulados, ...nuevos])),
      // Solo se guarda completo: si el buscador se cierra antes, la próxima vez se consulta de nuevo.
      tap({ complete: () => (this.cache = { usuario, hasta: Date.now() + VIGENCIA_MS, elementos: acumulados }) }),
    );
  }

  private deActivos(activos: ActivoInventario[]): ElementoBusqueda[] {
    return activos.map((a) =>
      elemento(
        {
          clave: `activo-${a.id}`,
          tipo: 'Activos',
          titulo: a.nombre,
          detalle: [a.codigo, a.tipo, a.ubicacion_nombre].filter(Boolean).join(' · '),
          ruta: ['/activos', a.id],
        },
        a.numero_serie,
        a.marca,
        a.modelo,
        a.responsable_nombre,
      ),
    );
  }

  /** Hosts de Zabbix: si están inventariados se abre su ficha; si no, la lista de Activos. */
  private deHosts(hosts: Activo[], activos: ActivoInventario[]): ElementoBusqueda[] {
    const inventario = new Map(activos.map((a) => [a.codigo.toLowerCase(), a]));
    return hosts.map((h) => {
      const activo = inventario.get(h.codigo.toLowerCase());
      return elemento(
        {
          clave: `host-${h.id}`,
          tipo: 'Servidores',
          titulo: h.codigo,
          detalle: [h.direccion, (h.grupo ?? []).join(', '), h.estado, activo ? null : 'sin inventariar']
            .filter(Boolean)
            .join(' · '),
          ruta: activo ? ['/activos', activo.id] : ['/activos'],
        },
        h.nombre,
      );
    });
  }

  private deSensores(sensores: EstadoSensor[]): ElementoBusqueda[] {
    return sensores.map((s) =>
      elemento(
        {
          clave: `sensor-${s.id}`,
          tipo: 'Sensores',
          titulo: s.sensorId,
          detalle: `${s.ubicacion} · ${s.temperatura} °C · ${s.humedad} % · ${s.conexion}`,
          ruta: ['/monitoreo'],
        },
        s.rack === 'sin rack' ? null : s.rack, // si no, "rack" encontraría todos los sensores sin rack
      ),
    );
  }

  private deZonas(zonas: UbicacionCatalogo[]): ElementoBusqueda[] {
    return zonas.map((z) =>
      elemento({
        clave: `zona-${z.id}`,
        tipo: 'Zonas',
        titulo: [z.sala, z.zona].filter(Boolean).join(' · '),
        detalle: [z.rack ? `rack ${z.rack}` : null, z.posicion ? `posición ${z.posicion}` : null, 'umbrales en Monitoreo']
          .filter(Boolean)
          .join(' · '),
        ruta: ['/monitoreo'],
      }),
    );
  }

  private deIntervenciones(intervenciones: Intervencion[]): ElementoBusqueda[] {
    return intervenciones.map((i) =>
      elemento(
        {
          clave: `intervencion-${i.id}`,
          tipo: 'Intervenciones',
          titulo: tituloIntervencion(i),
          detalle: [etiquetaEstadoIntervencion(i.estado), i.solicitante_nombre, i.responsable_nombre && `técnico ${i.responsable_nombre}`]
            .filter(Boolean)
            .join(' · '),
          ruta: ['/intervenciones'],
          queryParams: { id: i.id },
        },
        i.objetivo,
        i.impacto_esperado,
      ),
    );
  }

  /** Alertas abiertas ("eventos"): las de Zabbix llevan a la ficha del servidor; las del ambiente, a Monitoreo. */
  private deAlertas(alertas: Alerta[], activos: ActivoInventario[]): ElementoBusqueda[] {
    const inventario = new Map(activos.map((a) => [a.codigo.toLowerCase(), a]));
    return alertas.map((a) => {
      const activo = a.host ? inventario.get(a.host.toLowerCase()) : undefined;
      return elemento(
        {
          clave: `alerta-${a.id}`,
          tipo: 'Alertas',
          titulo: a.problema || a.condicion,
          detalle: [a.host ?? a.sensor_codigo, a.severidad, a.origen === 'Zabbix' ? 'Zabbix' : 'ambiente'].filter(Boolean).join(' · '),
          ruta: a.origen === 'Zabbix' ? (activo ? ['/activos', activo.id] : ['/activos']) : ['/monitoreo'],
        },
        a.evento_zabbix,
      );
    });
  }
}
