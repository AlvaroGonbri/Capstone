import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IonBadge,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonSkeletonText,
} from '@ionic/angular';
import { addIcons } from 'ionicons';
import {
  alertCircleOutline,
  arrowForwardOutline,
  buildOutline,
  cloudOfflineOutline,
  cubeOutline,
  fingerPrintOutline,
  serverOutline,
  thermometerOutline,
} from 'ionicons/icons';
import { catchError, forkJoin, of } from 'rxjs';
import { Activo, ActivoInventario, Alerta, EstadoSensor, EventoAcceso, Intervencion } from '../../core/models';
import { ActivosService } from '../../core/services/activos.service';
import { AuthService } from '../../core/services/auth.service';
import { AccesosService } from '../../core/services/accesos.service';
import { InventarioService, etiquetaCriticidad } from '../../core/services/inventario.service';
import {
  ESTADOS_CERRADOS,
  IntervencionesService,
  colorEstadoIntervencion,
  etiquetaEstadoIntervencion,
  tituloIntervencion,
} from '../../core/services/intervenciones.service';
import { MonitoreoService } from '../../core/services/monitoreo.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { GraficoAmbientalComponent, SensorGrafico } from '../../shared/grafico-ambiental.component';
import { HacePipe } from '../../shared/hace.pipe';

/** El backend filtra por fecha UTC: se piden desde ayer y el panel se queda con los de hoy (hora local). */
const DESDE_AYER = () => new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);

/** "1 por aprobar · 1 aprobada": solo los estados que tienen intervenciones. */
function detalleIntervenciones(abiertas: Intervencion[]): string {
  const contar = (...estados: Intervencion['estado'][]) => abiertas.filter((i) => estados.includes(i.estado)).length;
  const aprobadas = contar('Aprobada');
  const partes = [
    [contar('Pendiente', 'CambiosSolicitados'), 'por aprobar'],
    [aprobadas, aprobadas === 1 ? 'aprobada' : 'aprobadas'],
    [contar('EnEjecucion'), 'en ejecución'],
  ] as const;
  const texto = partes.filter(([n]) => n > 0).map(([n, etiqueta]) => `${n} ${etiqueta}`);
  return texto.length ? texto.join(' · ') : 'sin trabajos pendientes';
}

type Severidad = Alerta['severidad'];
type Nivel = 'critico' | 'advertencia' | 'info' | 'sin-datos';

/** Orden de gravedad (0 = más grave) y cómo se muestra cada severidad de Zabbix. */
const SEVERIDADES: Record<Severidad, { rango: number; nivel: Nivel; etiqueta: string; corta: string; color: string }> = {
  Critica: { rango: 0, nivel: 'critico', etiqueta: 'Crítica', corta: 'crítica', color: 'danger' },
  Alta: { rango: 1, nivel: 'critico', etiqueta: 'Alta', corta: 'alta', color: 'danger' },
  Advertencia: { rango: 2, nivel: 'advertencia', etiqueta: 'Adv.', corta: 'advertencia', color: 'warning' },
  Informativa: { rango: 3, nivel: 'info', etiqueta: 'Info', corta: 'info', color: 'medium' },
};
const RANGO_SIN_DATOS = 4;

/** Una fila de "Alertas abiertas": un problema de Zabbix (agrupado entre servidores) o un sensor. */
interface FilaAlerta {
  clave: string;
  titulo: string;
  detalle: string;
  /** Texto antes de la hora relativa, p. ej. "última lectura ". */
  prefijo: string;
  fecha: string;
  etiqueta: string;
  color: string;
  nivel: Nivel;
  rango: number;
  ruta: string;
}

interface Chip {
  texto: string;
  color: string;
}

/** Tarjeta de un servidor de Zabbix en el panel. */
interface TarjetaServidor {
  codigo: string;
  detalle: string;
  nivel: 'critico' | 'advertencia' | 'normal';
  chips: Chip[];
  ruta: (string | number)[];
}

const fechaAlerta = (a: Alerta) => a.fecha_ultima_ocurrencia ?? a.fecha_apertura;
const masReciente = (a: string, b: string) => (new Date(a) > new Date(b) ? a : b);

/** Cantidad por severidad, de la más grave a la menos: "2 alta", "1 advertencia". */
function chipsPorSeveridad(alertas: Alerta[]): Chip[] {
  const conteo = new Map<Severidad, number>();
  for (const a of alertas) {
    conteo.set(a.severidad, (conteo.get(a.severidad) ?? 0) + 1);
  }
  return [...conteo.entries()]
    .sort(([a], [b]) => SEVERIDADES[a].rango - SEVERIDADES[b].rango)
    .map(([severidad, n]) => ({ texto: `${n} ${SEVERIDADES[severidad].corta}`, color: SEVERIDADES[severidad].color }));
}

@Component({
  selector: 'app-panel',
  imports: [
    DatePipe,
    RouterLink,
    EncabezadoComponent,
    GraficoAmbientalComponent,
    HacePipe,
    IonBadge,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonIcon,
    IonItem,
    IonLabel,
    IonList,
    IonSkeletonText,
  ],
  templateUrl: './panel.page.html',
  styleUrl: './panel.page.scss',
})
export class PanelPage {
  private readonly inventarioService = inject(InventarioService);
  private readonly monitoreoService = inject(MonitoreoService);
  private readonly accesosService = inject(AccesosService);
  private readonly zabbixService = inject(ActivosService);
  private readonly auth = inject(AuthService);
  /** El Técnico no ve el registro de accesos. */
  protected readonly veAccesos = !this.auth.tieneRol('tecnico');
  /** App móvil (solo consulta): el KPI de Alertas reemplaza al de Accesos. */
  protected readonly movil = this.auth.soloConsulta;
  private readonly intervencionesService = inject(IntervencionesService);

  protected readonly cargando = signal(true);
  /** Inventario sin los retirados (RF-ACT). */
  private readonly activos = signal<ActivoInventario[]>([]);
  private readonly sensores = signal<EstadoSensor[]>([]);
  private readonly accesos = signal<EventoAcceso[]>([]);
  private readonly intervenciones = signal<Intervencion[]>([]);
  /** Servidores de Zabbix; null si no se pudo consultar (el resto del panel se muestra igual). */
  private readonly hosts = signal<Activo[] | null>(null);
  /** Alertas de infraestructura abiertas (RF-INF-02). */
  private readonly alertasZabbix = signal<Alerta[]>([]);

  protected readonly resumen = computed(() => {
    const hoy = new Date().toDateString();
    const accesosHoy = this.accesos().filter(
      (a) => new Date(a.fecha_hora).toDateString() === hoy,
    );
    const sinDatos = this.sinDatos();
    return {
      activosTotales: this.activos().length,
      activosOperativos: this.activos().filter((a) => a.estado === 'Operativo').length,
      activosEnFalla: this.activos().filter((a) => a.estado === 'Degradado' || a.estado === 'Fuera_de_servicio').length,
      activosEnMantenimiento: this.activos().filter((a) => a.estado === 'En_mantenimiento').length,
      sensoresEnAlerta: this.fueraDeRango().length,
      sensoresSinDatos: sinDatos.length,
      /** Con un solo sensor sin datos se dice desde cuándo no reporta. */
      ultimaLecturaSinDatos: sinDatos.length === 1 ? sinDatos[0].actualizadoEn : null,
      accesosHoy: accesosHoy.length,
      accesosDenegadosHoy: accesosHoy.filter((a) => a.resultado === 'Denegado').length,
      fallasLectorHoy: accesosHoy.filter((a) => a.resultado === 'Error').length,
      intervencionesAbiertas: this.trabajosAbiertos().length,
      detalleIntervenciones: detalleIntervenciones(this.trabajosAbiertos()),
      alertasAbiertas: this.alertasZabbix().length + this.fueraDeRango().length,
      problemasZabbix: this.alertasZabbix().length,
    };
  });

  /**
   * "Sin datos ≠ alerta": un sensor que dejó de reportar no cuenta como "en alerta" aunque su
   * última lectura estuviera fuera de rango; se muestra aparte como sensor sin reportar.
   */
  private readonly fueraDeRango = computed(() =>
    this.sensores().filter((s) => s.conexion === 'En línea' && s.nivel !== 'normal'),
  );
  private readonly sinDatos = computed(() => this.sensores().filter((s) => s.conexion === 'Sin datos'));

  /** Sensores para el gráfico de temperatura y humedad: primero los que están reportando. */
  protected readonly sensoresGrafico = computed<SensorGrafico[]>(() =>
    [...this.sensores()]
      .sort((a, b) => Number(b.conexion === 'En línea') - Number(a.conexion === 'En línea'))
      .map((s) => ({ id: s.id, codigo: s.sensorId, ubicacion: s.ubicacion })),
  );

  /**
   * Alertas abiertas en una sola lista: las de Zabbix (un mismo problema en varios servidores
   * va en una fila) y las del ambiente. Primero las más graves; dentro de cada nivel, las recientes.
   */
  protected readonly alertas = computed<FilaAlerta[]>(() => {
    const grupos = new Map<string, Alerta[]>();
    for (const a of this.alertasZabbix()) {
      const problema = a.problema || a.condicion;
      grupos.set(problema, [...(grupos.get(problema) ?? []), a]);
    }
    const zabbix = [...grupos.entries()].map(([problema, alertas]): FilaAlerta => {
      const peor = alertas.reduce((p, a) => (SEVERIDADES[a.severidad].rango < SEVERIDADES[p].rango ? a.severidad : p), alertas[0].severidad);
      const hosts = [...new Set(alertas.map((a) => a.host ?? 'Zabbix'))];
      const detalle =
        alertas.length === 1 ? hosts[0]
        : hosts.length > 1 ? `${hosts.join(' · ')} · ${alertas.length} eventos agrupados`
        : `${hosts[0]} · ${alertas.length} eventos`;
      return {
        clave: `zabbix-${problema}`,
        titulo: problema,
        detalle,
        prefijo: '',
        fecha: alertas.map(fechaAlerta).reduce(masReciente),
        etiqueta: SEVERIDADES[peor].etiqueta,
        color: SEVERIDADES[peor].color,
        nivel: SEVERIDADES[peor].nivel,
        rango: SEVERIDADES[peor].rango,
        ruta: '/activos',
      };
    });
    const ambiente = this.fueraDeRango().map((s): FilaAlerta => {
      const motivo = s.motivos.join(' y ') || 'fuera de rango';
      return {
        clave: `sensor-${s.sensorId}`,
        titulo: motivo.charAt(0).toUpperCase() + motivo.slice(1),
        detalle: `${s.sensorId} · ${s.ubicacion} · ${s.temperatura} °C · ${s.humedad} %`,
        prefijo: '',
        fecha: s.actualizadoEn,
        etiqueta: 'Fuera de rango',
        color: 'danger',
        nivel: 'critico',
        rango: SEVERIDADES.Alta.rango,
        ruta: '/monitoreo',
      };
    });
    const sinDatos = this.sinDatos().map((s): FilaAlerta => ({
      clave: `sin-datos-${s.sensorId}`,
      titulo: 'Sensor sin reportar',
      detalle: `${s.sensorId} · ${s.ubicacion}`,
      prefijo: 'última lectura ',
      fecha: s.actualizadoEn,
      etiqueta: 'Sin datos',
      color: 'medium',
      nivel: 'sin-datos',
      rango: RANGO_SIN_DATOS,
      ruta: '/monitoreo',
    }));
    return [...zabbix, ...ambiente, ...sinDatos].sort(
      (a, b) => a.rango - b.rango || new Date(b.fecha).getTime() - new Date(a.fecha).getTime(),
    );
  });

  /** Resumen en la cabecera de la lista: "2 alta · 3 adv. · 1 sin datos" (alertas individuales). */
  protected readonly chipsAlertas = computed<Chip[]>(() => {
    const zabbix = this.alertasZabbix();
    const contar = (...severidades: Severidad[]) => zabbix.filter((a) => severidades.includes(a.severidad)).length;
    const chips = [
      { n: contar('Critica', 'Alta') + this.fueraDeRango().length, texto: 'alta', color: 'danger' },
      { n: contar('Advertencia'), texto: 'adv.', color: 'warning' },
      { n: contar('Informativa'), texto: 'info', color: 'medium' },
      { n: this.sinDatos().length, texto: 'sin datos', color: 'medium' },
    ];
    return chips.filter((c) => c.n > 0).map((c) => ({ texto: `${c.n} ${c.texto}`, color: c.color }));
  });

  /** Servidores de Zabbix con sus problemas abiertos por severidad; null si Zabbix no respondió. */
  protected readonly servidores = computed<TarjetaServidor[] | null>(() => {
    const hosts = this.hosts();
    if (hosts === null) {
      return null;
    }
    const alertasPorHost = new Map<string, Alerta[]>();
    for (const a of this.alertasZabbix()) {
      const clave = (a.host ?? '').toLowerCase();
      alertasPorHost.set(clave, [...(alertasPorHost.get(clave) ?? []), a]);
    }
    const inventario = new Map(this.activos().map((a) => [a.codigo.toLowerCase(), a]));
    return hosts.map((h): TarjetaServidor => {
      const alertas = alertasPorHost.get(h.codigo.toLowerCase()) ?? [];
      const activo = inventario.get(h.codigo.toLowerCase());
      const rol =
        h.mysqlEsPrimario === null || h.mysqlEsPrimario === undefined
          ? (h.grupo ?? []).join(', ')
          : `${h.mysqlEsPrimario ? 'Primario' : 'Secundario'} · Group Replication`;
      const peor = Math.min(...alertas.map((a) => SEVERIDADES[a.severidad].rango), RANGO_SIN_DATOS);
      let chips = chipsPorSeveridad(alertas);
      if (chips.length === 0) {
        chips = [
          h.estado === 'en falla' ? { texto: 'En falla', color: 'danger' }
          : h.estado === 'en mantencion' ? { texto: 'En mantención', color: 'warning' }
          : { texto: 'Sin problemas', color: 'success' },
        ];
      }
      return {
        codigo: h.codigo,
        detalle: [rol, activo ? `criticidad ${etiquetaCriticidad(activo.criticidad).toLowerCase()}` : null]
          .filter(Boolean)
          .join(' · '),
        nivel:
          h.estado === 'en falla' || peor <= SEVERIDADES.Alta.rango ? 'critico'
          : h.estado === 'en mantencion' || peor === SEVERIDADES.Advertencia.rango ? 'advertencia'
          : 'normal',
        chips,
        ruta: activo ? ['/activos', activo.id] : ['/activos'],
      };
    });
  });

  protected readonly trabajosAbiertos = computed(() =>
    this.intervenciones().filter((i) => !ESTADOS_CERRADOS.includes(i.estado)),
  );
  protected readonly etiquetaIntervencion = etiquetaEstadoIntervencion;
  protected readonly tituloIntervencion = tituloIntervencion;
  protected readonly colorIntervencion = colorEstadoIntervencion;

  constructor() {
    addIcons({
      alertCircleOutline,
      cloudOfflineOutline,
      thermometerOutline,
      arrowForwardOutline,
      cubeOutline,
      buildOutline,
      fingerPrintOutline,
      serverOutline,
    });

    forkJoin({
      activos: this.inventarioService.listar(),
      sensores: this.monitoreoService.estadoSensores(),
      accesos: this.veAccesos
        ? this.accesosService.eventos({ desde: DESDE_AYER() }).pipe(catchError(() => of([])))
        : of([]),
      intervenciones: this.intervencionesService.listar(),
      // Si Zabbix o su sincronización fallan, el resto del panel se muestra igual.
      hosts: this.zabbixService.listar().pipe(catchError(() => of(null))),
      alertasZabbix: this.zabbixService.alertasAbiertas().pipe(catchError(() => of([] as Alerta[]))),
    }).subscribe((datos) => {
      this.activos.set(datos.activos);
      this.sensores.set(datos.sensores);
      this.accesos.set(datos.accesos);
      this.intervenciones.set(datos.intervenciones);
      this.hosts.set(datos.hosts);
      this.alertasZabbix.set(datos.alertasZabbix);
      this.cargando.set(false);
    });
  }
}
