import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { addIcons } from 'ionicons';
import { warningOutline } from 'ionicons/icons';
import {
  IonBadge,
  IonButton,
  IonButtons,
  IonContent,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSearchbar,
  IonSegment,
  IonSegmentButton,
  IonSelect,
  IonSelectOption,
  IonSkeletonText,
  IonToggle,
} from '@ionic/angular';
import {
  Activo,
  ActivoInventario,
  Alerta,
  EstadoInventario,
  SincronizacionZabbix,
  TipoActivoCatalogo,
  UbicacionCatalogo,
} from '../../core/models';
import { ActivosService } from '../../core/services/activos.service';
import { AlertasService } from '../../core/services/alertas.service';
import { AuthService } from '../../core/services/auth.service';
import { CatalogosService, nombreUbicacion } from '../../core/services/catalogos.service';
import { ESTADO_RETIRADO, InventarioService, colorCriticidad, etiquetaCriticidad } from '../../core/services/inventario.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { HacePipe } from '../../shared/hace.pipe';
import { environment } from '../../../environments/environment';

type FiltroEstado = 'todos' | EstadoInventario;
type Columna = 'nombre' | 'tipo' | 'ubicacion' | 'responsable' | 'criticidad' | 'zabbix' | 'estado';

/** Con más activos, la tabla se pagina de a 25 (el encabezado queda fijo al desplazarse). */
const POR_PAGINA = 25;
const RANGO_CRITICIDAD: Record<string, number> = { Baja: 0, Media: 1, Alta: 2, Critica: 3 };

@Component({
  selector: 'app-activos',
  imports: [
    DatePipe,
    RouterLink,
    EncabezadoComponent,
    HacePipe,
    IonBadge,
    IonButton,
    IonButtons,
    IonContent,
    IonIcon,
    IonItem,
    IonLabel,
    IonList,
    IonNote,
    IonSearchbar,
    IonSegment,
    IonSegmentButton,
    IonSelect,
    IonSelectOption,
    IonSkeletonText,
    IonToggle,
  ],
  templateUrl: './activos.page.html',
  styleUrl: './activos.page.scss',
})
export class ActivosPage {
  private readonly inventario = inject(InventarioService);
  private readonly zabbix = inject(ActivosService);
  private readonly catalogos = inject(CatalogosService);
  private readonly destroyRef = inject(DestroyRef);

  /** RF-ACT-01: registran y editan Administrador y Técnico; el resto solo consulta. */
  protected readonly puedeEditar = inject(AuthService).puedeModificar('administrador', 'administradorprivilegiado', 'tecnico');

  protected readonly cargando = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly activos = signal<ActivoInventario[]>([]);
  protected readonly hosts = signal<Activo[]>([]);
  protected readonly zabbixDisponible = signal(true);
  /** Alertas de infraestructura abiertas, registradas desde Zabbix (RF-INF-02). */
  protected readonly alertas = signal<Alerta[]>([]);
  protected readonly tipos = signal<TipoActivoCatalogo[]>([]);
  protected readonly ubicaciones = signal<UbicacionCatalogo[]>([]);

  protected readonly busqueda = signal('');
  protected readonly filtroEstado = signal<FiltroEstado>('todos');
  protected readonly filtroTipo = signal<string>('');
  protected readonly filtroUbicacion = signal<number | null>(null);
  protected readonly incluirRetirados = signal(false);

  protected readonly actualizadoEn = signal<Date | null>(null);
  protected readonly sincronizacion = signal<SincronizacionZabbix | null>(null);
  protected readonly refrescoSegundos = environment.refrescoInfraestructuraMs / 1000;
  protected readonly estados = computed(() =>
    this.inventario.estadosSeleccionables().filter((e) => e.nombre !== ESTADO_RETIRADO),
  );
  protected readonly etiquetaEstado = (estado: EstadoInventario) => this.inventario.etiquetaEstado(estado);
  protected readonly colorEstado = (estado: EstadoInventario) => this.inventario.colorEstado(estado);
  protected readonly nombreUbicacion = nombreUbicacion;

  /** Host de Zabbix por código en minúsculas: el activo se vincula si su código coincide. */
  private readonly hostPorCodigo = computed(
    () => new Map(this.hosts().map((h) => [h.codigo.toLowerCase(), h])),
  );

  protected readonly filtrados = computed(() => {
    const texto = this.busqueda().trim().toLowerCase();
    const estado = this.filtroEstado();
    const tipo = this.filtroTipo();
    const ubicacion = this.filtroUbicacion();
    return this.activos().filter((a) =>
      (estado === 'todos' || a.estado === estado) &&
      (!tipo || a.tipo === tipo) &&
      (ubicacion === null || a.ubicacion === ubicacion) &&
      (texto === '' ||
        [a.codigo, a.nombre, a.numero_serie, a.marca, a.modelo, a.ubicacion_nombre, a.responsable_nombre]
          .join(' ')
          .toLowerCase()
          .includes(texto)),
    );
  });

  // ------------------------------------------------- orden y páginas
  protected readonly columnas: Array<{ columna: Columna; titulo: string }> = [
    { columna: 'nombre', titulo: 'Activo' },
    { columna: 'tipo', titulo: 'Tipo' },
    { columna: 'ubicacion', titulo: 'Ubicación' },
    { columna: 'responsable', titulo: 'Responsable' },
    { columna: 'criticidad', titulo: 'Criticidad' },
    { columna: 'zabbix', titulo: 'Zabbix' },
    { columna: 'estado', titulo: 'Estado' },
  ];
  protected readonly orden = signal<{ columna: Columna; asc: boolean }>({ columna: 'nombre', asc: true });
  protected readonly pagina = signal(0);

  protected readonly ordenados = computed(() => {
    const { columna, asc } = this.orden();
    const valor = (a: ActivoInventario): string | number => {
      switch (columna) {
        case 'tipo': return a.tipo ?? '';
        case 'ubicacion': return a.ubicacion_nombre;
        case 'responsable': return a.responsable_nombre ?? '';
        case 'criticidad': return RANGO_CRITICIDAD[a.criticidad] ?? 0;
        case 'zabbix': return this.host(a)?.problemasActivos ?? -1; // sin monitoreo, al final
        case 'estado': return this.etiquetaEstado(a.estado);
        default: return a.nombre;
      }
    };
    const signo = asc ? 1 : -1;
    return [...this.filtrados()].sort((a, b) => {
      const va = valor(a);
      const vb = valor(b);
      const comparacion = typeof va === 'number' && typeof vb === 'number'
        ? va - vb
        : String(va).localeCompare(String(vb), 'es', { sensitivity: 'base' });
      return comparacion * signo || a.nombre.localeCompare(b.nombre, 'es');
    });
  });

  protected readonly paginas = computed(() => Math.max(1, Math.ceil(this.ordenados().length / POR_PAGINA)));
  /** Si los filtros dejan menos páginas, se muestra la última que existe. */
  protected readonly paginaActual = computed(() => Math.min(this.pagina(), this.paginas() - 1));
  protected readonly visibles = computed(() => {
    const desde = this.paginaActual() * POR_PAGINA;
    return this.ordenados().slice(desde, desde + POR_PAGINA);
  });

  protected ordenarPor(columna: Columna): void {
    this.orden.update((o) => (o.columna === columna ? { columna, asc: !o.asc } : { columna, asc: true }));
    this.pagina.set(0);
  }

  /** Valor de aria-sort de la columna (para lectores de pantalla). */
  protected sentido(columna: Columna): 'ascending' | 'descending' | 'none' {
    const o = this.orden();
    return o.columna !== columna ? 'none' : o.asc ? 'ascending' : 'descending';
  }

  protected irAPagina(n: number): void {
    this.pagina.set(Math.max(0, Math.min(n, this.paginas() - 1)));
  }

  /** Equipos que Zabbix monitorea y aún no están en el inventario. */
  protected readonly sinInventariar = computed(() => {
    const codigos = new Set(this.activos().map((a) => a.codigo.toLowerCase()));
    return this.hosts().filter((h) => !codigos.has(h.codigo.toLowerCase()));
  });

  constructor() {
    addIcons({ warningOutline });
    // Al cambiar un filtro se vuelve a la primera página (la recarga periódica de Zabbix no la cambia).
    effect(() => {
      this.busqueda();
      this.filtroEstado();
      this.filtroTipo();
      this.filtroUbicacion();
      this.incluirRetirados();
      untracked(() => this.pagina.set(0));
    });
    this.catalogos.ubicaciones().subscribe((lista) => this.ubicaciones.set(lista));
    this.inventario.tipos().subscribe((lista) => this.tipos.set(lista));
    this.cargar();

    // RF-INF-01: el estado de los servidores se vuelve a consultar cada minuto.
    const temporizador = setInterval(() => {
      if (!document.hidden) {
        this.cargar();
      }
    }, environment.refrescoInfraestructuraMs);
    this.destroyRef.onDestroy(() => clearInterval(temporizador));
  }

  protected host(activo: ActivoInventario): Activo | undefined {
    return this.hostPorCodigo().get(activo.codigo.toLowerCase());
  }

  protected colorZabbix(host: Activo): string {
    return host.estado === 'operativo' ? 'success' : host.estado === 'en mantencion' ? 'warning' : 'danger';
  }

  protected colorSeveridad(severidad: Alerta['severidad']): string {
    return severidad === 'Critica' || severidad === 'Alta' ? 'danger' : severidad === 'Advertencia' ? 'warning' : 'medium';
  }

  // ------------------------------------------------- presentación
  /** Las alertas de Zabbix se muestran resumidas; el detalle se despliega a pedido. */
  protected readonly alertasDesplegadas = signal(false);

  protected readonly alertasPorSeveridad = computed(() => {
    const conteo = new Map<string, number>();
    for (const a of this.alertas()) {
      conteo.set(a.severidad, (conteo.get(a.severidad) ?? 0) + 1);
    }
    return [...conteo.entries()].map(([severidad, cantidad]) => ({
      severidad: severidad as Alerta['severidad'],
      cantidad,
    }));
  });

  protected readonly colorCriticidad = colorCriticidad;
  protected readonly etiquetaCriticidad = etiquetaCriticidad;

  /** Cantidad de activos por estado, para las pestañas ("Operativo 2"). */
  protected readonly conteoPorEstado = computed(() => {
    const conteo = new Map<string, number>();
    for (const a of this.activos()) {
      conteo.set(a.estado, (conteo.get(a.estado) ?? 0) + 1);
    }
    return conteo;
  });

  /** La alerta de infraestructura más reciente, para la franja resumida. */
  protected readonly ultimaAlerta = computed(() => {
    const fecha = (a: Alerta) => new Date(a.fecha_ultima_ocurrencia ?? a.fecha_apertura).getTime();
    return [...this.alertas()].sort((a, b) => fecha(b) - fecha(a))[0] ?? null;
  });

  protected cambiarIncluirRetirados(valor: boolean): void {
    this.incluirRetirados.set(valor);
    this.cargarInventario();
  }

  private cargar(): void {
    this.cargarInventario();
    this.zabbix.listar().subscribe({
      next: (hosts) => {
        this.hosts.set(hosts);
        this.zabbixDisponible.set(true);
        this.actualizadoEn.set(new Date());
      },
      error: () => this.zabbixDisponible.set(false), // el inventario se sigue mostrando (CA-03)
    });
    this.zabbix.sincronizacion().subscribe({
      next: (estado) => this.sincronizacion.set(estado),
      error: () => this.sincronizacion.set(null),
    });
    this.zabbix.alertasAbiertas().subscribe({
      next: (alertas) => this.alertas.set(alertas),
      error: () => undefined,
    });
  }

  private cargarInventario(): void {
    this.inventario.listar({ incluir_retirados: this.incluirRetirados() }).subscribe({
      next: (lista) => {
        this.activos.set(lista);
        this.error.set(null);
        this.cargando.set(false);
      },
      error: () => {
        this.error.set('No fue posible cargar el inventario de activos.');
        this.cargando.set(false);
      },
    });
  }

  // ------------------------------------------------- gestión de alertas
  /** Reconocen y cierran alertas el Técnico y el Administrador. */
  protected readonly puedeGestionarAlertas = inject(AuthService).puedeModificar('administrador', 'administradorprivilegiado', 'tecnico');
  private readonly alertasService = inject(AlertasService);

  protected reconocerAlerta(alerta: Alerta): void {
    this.alertasService.reconocer(alerta.id).subscribe({
      next: (a) => this.alertas.update((lista) => lista.map((x) => (x.id === a.id ? a : x))),
      error: () => undefined,
    });
  }

  protected cerrarAlerta(alerta: Alerta): void {
    const comentario = prompt('Comentario del cierre (opcional): qué se hizo') ?? null;
    if (comentario === null) {
      return;
    }
    this.alertasService.cerrar(alerta.id, comentario).subscribe({
      next: () => this.alertas.update((lista) => lista.filter((x) => x.id !== alerta.id)),
      error: () => undefined,
    });
  }

}
