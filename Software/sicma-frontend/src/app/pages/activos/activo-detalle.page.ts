import { DatePipe } from '@angular/common';
import { Component, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  IonBackButton,
  IonBadge,
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonHeader,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSegment,
  IonSegmentButton,
  IonSkeletonText,
  IonTitle,
  IonToolbar,
} from '@ionic/angular';
import { Activo, ActivoInventario, EventoTecnico, HistorialActivo, Intervencion } from '../../core/models';
import { ActivosService } from '../../core/services/activos.service';
import { AuthService } from '../../core/services/auth.service';
import { IntervencionesService } from '../../core/services/intervenciones.service';
import { InventarioService, colorEstado, etiquetaEstado } from '../../core/services/inventario.service';

/** Nombre legible de cada campo del historial (RF-ACT-03). */
const CAMPOS: Record<string, string> = {
  alta: 'Alta en el inventario',
  codigo: 'Código',
  nombre: 'Nombre',
  tipo: 'Tipo',
  marca: 'Marca',
  modelo: 'Modelo',
  numero_serie: 'Número de serie',
  estado: 'Estado',
  criticidad: 'Criticidad',
  ubicacion: 'Ubicación',
  responsable: 'Responsable',
  observaciones: 'Observaciones',
};

@Component({
  selector: 'app-activo-detalle',
  imports: [
    DatePipe,
    RouterLink,
    IonBackButton,
    IonBadge,
    IonButton,
    IonButtons,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonHeader,
    IonItem,
    IonLabel,
    IonList,
    IonNote,
    IonSegment,
    IonSegmentButton,
    IonSkeletonText,
    IonTitle,
    IonToolbar,
  ],
  templateUrl: './activo-detalle.page.html',
})
export class ActivoDetallePage {
  /** Id del inventario. Llega desde la ruta gracias a withComponentInputBinding(). */
  readonly id = input.required<string>();

  private readonly inventario = inject(InventarioService);
  private readonly zabbix = inject(ActivosService);
  private readonly intervencionesService = inject(IntervencionesService);
  protected readonly puedeEditar = inject(AuthService).tieneRol('administrador', 'administradorprivilegiado', 'tecnico');

  protected readonly activo = signal<ActivoInventario | undefined>(undefined);
  protected readonly cargando = signal(true);
  protected readonly cambios = signal<HistorialActivo[]>([]);
  protected readonly intervenciones = signal<Intervencion[]>([]);
  protected readonly etiquetaEstado = etiquetaEstado;
  protected readonly colorEstado = colorEstado;

  /** Host de Zabbix con el mismo código (null = no monitoreado; undefined = aún consultando). */
  protected readonly host = signal<Activo | null | undefined>(undefined);
  protected readonly zabbixDisponible = signal(true);
  protected readonly periodos = [7, 30, 90];
  protected readonly dias = signal(30);
  protected readonly eventos = signal<EventoTecnico[]>([]);
  protected readonly cargandoEventos = signal(false);
  protected readonly errorEventos = signal<string | null>(null);

  constructor() {
    queueMicrotask(() => {
      const id = Number(this.id());
      this.inventario.obtener(id).subscribe({
        next: (activo) => {
          this.activo.set(activo);
          this.cargando.set(false);
          this.buscarHost(activo.codigo);
        },
        error: () => this.cargando.set(false),
      });
      this.inventario.historial(id).subscribe({ next: (lista) => this.cambios.set(lista), error: () => undefined });
      this.intervencionesService.listarPorActivo(id).subscribe((lista) => this.intervenciones.set(lista));
    });
  }

  protected campo(nombre: string): string {
    return CAMPOS[nombre] ?? nombre;
  }

  protected valor(texto: string | null): string {
    return texto ? (etiquetaEstadoSiAplica(texto)) : '—';
  }

  protected cambiarPeriodo(valor: unknown): void {
    const dias = Number(valor);
    const host = this.host();
    if (!this.periodos.includes(dias) || dias === this.dias() || !host) {
      return;
    }
    this.dias.set(dias);
    this.cargarEventos(host.id);
  }

  protected colorZabbix(host: Activo): string {
    return host.estado === 'operativo' ? 'success' : host.estado === 'en mantencion' ? 'warning' : 'danger';
  }

  protected colorSeveridad(severidad: number): string {
    if (severidad >= 4) {
      return 'danger';
    }
    return severidad >= 2 ? 'warning' : 'medium';
  }

  protected duracion(segundos: number | null): string {
    if (segundos === null) {
      return 'en curso';
    }
    const minutos = Math.round(segundos / 60);
    if (minutos < 60) {
      return `${minutos} min`;
    }
    const horas = Math.floor(minutos / 60);
    if (horas < 24) {
      return `${horas} h ${minutos % 60} min`;
    }
    return `${Math.floor(horas / 24)} d ${horas % 24} h`;
  }

  private buscarHost(codigo: string): void {
    this.zabbix.listar().subscribe({
      next: (hosts) => {
        const host = hosts.find((h) => h.codigo.toLowerCase() === codigo.toLowerCase()) ?? null;
        this.host.set(host);
        if (host) {
          this.cargarEventos(host.id);
        }
      },
      error: () => {
        this.zabbixDisponible.set(false);
        this.host.set(null);
      },
    });
  }

  private cargarEventos(hostId: number): void {
    this.cargandoEventos.set(true);
    this.errorEventos.set(null);
    this.zabbix.eventos(hostId, this.dias()).subscribe({
      next: (eventos) => {
        this.eventos.set(eventos);
        this.cargandoEventos.set(false);
      },
      error: () => {
        this.eventos.set([]);
        this.errorEventos.set('No fue posible consultar el historial en Zabbix.');
        this.cargandoEventos.set(false);
      },
    });
  }
}

/** Los estados se guardan como 'En_mantenimiento'; en el historial se muestran legibles. */
function etiquetaEstadoSiAplica(texto: string): string {
  return texto.includes('_') ? texto.replaceAll('_', ' ') : texto;
}
