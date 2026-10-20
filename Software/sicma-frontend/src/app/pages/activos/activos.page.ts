import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IonBadge,
  IonButton,
  IonButtons,
  IonContent,
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
import { AuthService } from '../../core/services/auth.service';
import { CatalogosService, nombreUbicacion } from '../../core/services/catalogos.service';
import { ESTADO_RETIRADO, InventarioService } from '../../core/services/inventario.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { environment } from '../../../environments/environment';

type FiltroEstado = 'todos' | EstadoInventario;

@Component({
  selector: 'app-activos',
  imports: [
    DatePipe,
    RouterLink,
    EncabezadoComponent,
    IonBadge,
    IonButton,
    IonButtons,
    IonContent,
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

  /** Equipos que Zabbix monitorea y aún no están en el inventario. */
  protected readonly sinInventariar = computed(() => {
    const codigos = new Set(this.activos().map((a) => a.codigo.toLowerCase()));
    return this.hosts().filter((h) => !codigos.has(h.codigo.toLowerCase()));
  });

  constructor() {
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
}
