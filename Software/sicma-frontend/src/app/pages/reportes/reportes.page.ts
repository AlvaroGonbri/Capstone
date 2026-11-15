import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import {
  IonButton,
  IonCard,
  IonContent,
  IonInput,
  IonNote,
  IonSegment,
  IonSegmentButton,
  IonLabel,
  IonSelect,
  IonSelectOption,
  IonSpinner,
} from '@ionic/angular';
import { EstadoIntervencion, FiltroReporte, NivelEvento, ReportePeriodo, UbicacionCatalogo } from '../../core/models';
import { AuthService } from '../../core/services/auth.service';
import { CatalogosService, nombreUbicacion } from '../../core/services/catalogos.service';
import { etiquetaEstadoIntervencion } from '../../core/services/intervenciones.service';
import { ReportesService } from '../../core/services/reportes.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { GraficoDisponibilidadComponent } from '../../shared/grafico-disponibilidad.component';

type Nivel = NivelEvento;

interface Kpi {
  titulo: string;
  valor: string;
  unidad?: string;
  detalle: string;
  nivel: Nivel;
}

const numero = new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1 });
const DIAS_POR_DEFECTO = 30;

/** Fecha local AAAA-MM-DD (la del navegador, que en SICMA es la de Chile). */
function fechaLocal(fecha: Date): string {
  const desfase = fecha.getTimezoneOffset() * 60_000;
  return new Date(fecha.getTime() - desfase).toISOString().slice(0, 10);
}

function haceDias(dias: number): string {
  const f = new Date();
  f.setDate(f.getDate() - dias);
  return fechaLocal(f);
}

function textoFecha(iso: string): string {
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}-${m}-${a}`;
}

/**
 * Reportes del período (RF-BI): cifras de ambiente, servidores, alertas, intervenciones y accesos, con un
 * resumen en palabras (IA o plantilla) y el PDF que genera el servidor. En la app móvil (solo consulta)
 * muestra los últimos 30 días, sin filtros ni exportación.
 */
@Component({
  selector: 'app-reportes',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    EncabezadoComponent,
    GraficoDisponibilidadComponent,
    IonButton,
    IonCard,
    IonContent,
    IonInput,
    IonLabel,
    IonNote,
    IonSegment,
    IonSegmentButton,
    IonSelect,
    IonSelectOption,
    IonSpinner,
  ],
  templateUrl: './reportes.page.html',
  styleUrl: './reportes.page.scss',
})
export class ReportesPage {
  private readonly servicio = inject(ReportesService);
  private readonly catalogos = inject(CatalogosService);
  protected readonly movil = inject(AuthService).soloConsulta;

  protected readonly filtros = new FormGroup({
    desde: new FormControl(haceDias(DIAS_POR_DEFECTO - 1), { nonNullable: true }),
    hasta: new FormControl(fechaLocal(new Date()), { nonNullable: true }),
    zona: new FormControl<number | null>(null),
  });
  protected readonly hoy = fechaLocal(new Date());

  protected readonly ubicaciones = signal<UbicacionCatalogo[]>([]);
  protected readonly reporte = signal<ReportePeriodo | null>(null);
  protected readonly cargando = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly generandoPdf = signal(false);
  protected readonly errorPdf = signal<string | null>(null);
  protected readonly vista = signal<'dia' | 'host'>('dia');

  protected readonly nombreUbicacion = nombreUbicacion;
  protected readonly textoFecha = textoFecha;

  protected readonly kpis = computed<Kpi[]>(() => {
    const r = this.reporte();
    if (!r) return [];
    const d = r.disponibilidad.porcentaje;
    const a = r.alertas_ambientales;
    const z = r.problemas_zabbix;
    const i = r.intervenciones;
    const ac = r.accesos;
    return [
      {
        titulo: 'Disponibilidad',
        valor: d === null ? 'Sin datos' : numero.format(d),
        unidad: d === null ? undefined : '%',
        detalle: 'servidores · agente de Zabbix',
        nivel: d === null ? 'neutro' : d >= 99 ? 'ok' : d >= 95 ? 'advertencia' : 'critico',
      },
      {
        titulo: 'Alertas ambientales',
        valor: String(a.total),
        detalle:
          a.resolucion_promedio_min !== null
            ? `resueltas en ${numero.format(a.resolucion_promedio_min)} min en promedio`
            : a.total
              ? 'sin tiempo de resolución registrado'
              : 'ninguna en el período',
        nivel: a.total === 0 ? 'ok' : (a.por_severidad['Critica'] ?? 0) + (a.por_severidad['Alta'] ?? 0) ? 'critico' : 'advertencia',
      },
      {
        titulo: 'Problemas Zabbix',
        valor: String(z.total),
        detalle: `${z.altos_o_criticos} altos o críticos · ${z.abiertos_al_cierre} abiertos`,
        nivel: z.altos_o_criticos ? 'critico' : z.total ? 'advertencia' : 'ok',
      },
      {
        titulo: 'Intervenciones',
        valor: String(i.cerradas),
        unidad: `/${i.total}`,
        detalle: `cerradas de las solicitadas · ${i.abiertas} abiertas`,
        nivel: 'neutro',
      },
      {
        titulo: 'Accesos permitidos',
        valor: String(ac.permitidos),
        detalle: `${ac.denegados} denegados · ${ac.fallas_del_lector} fallas del lector`,
        nivel: ac.denegados ? 'advertencia' : 'neutro',
      },
    ];
  });

  /** Intervenciones por estado, de mayor a menor; las barras parten en cero. */
  protected readonly estados = computed(() => {
    const r = this.reporte();
    if (!r) return [];
    const filas = Object.entries(r.intervenciones.por_estado).sort((a, b) => b[1] - a[1]);
    const maximo = Math.max(1, ...filas.map(([, n]) => n));
    return filas.map(([estado, n]) => ({
      etiqueta: etiquetaEstadoIntervencion(estado as EstadoIntervencion),
      n,
      ancho: (100 * n) / maximo,
    }));
  });

  constructor() {
    if (!this.movil) {
      this.catalogos.ubicaciones().subscribe({ next: (u) => this.ubicaciones.set(u), error: () => undefined });
    }
    this.cargar();
  }

  private filtro(): FiltroReporte {
    if (this.movil) return {}; // el servidor usa los últimos 30 días
    const { desde, hasta, zona } = this.filtros.getRawValue();
    return { desde, hasta, zona };
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.error.set(null);
    this.servicio.resumen(this.filtro()).subscribe({
      next: (r) => {
        this.reporte.set(r);
        this.cargando.set(false);
      },
      error: (e: HttpErrorResponse) => {
        const detalle = e.error?.desde?.[0] ?? e.error?.hasta?.[0] ?? e.error?.zona?.[0] ?? e.error?.detail;
        this.error.set(detalle ?? 'No fue posible generar el reporte.');
        this.cargando.set(false);
      },
    });
  }

  protected exportarPdf(): void {
    const r = this.reporte();
    if (!r || this.generandoPdf()) return;
    this.generandoPdf.set(true);
    this.errorPdf.set(null);
    this.servicio.pdf(this.filtro()).subscribe({
      next: (archivo) => {
        const enlace = document.createElement('a');
        enlace.href = URL.createObjectURL(archivo);
        enlace.download = `SICMA-reporte-${r.periodo.desde}_${r.periodo.hasta}.pdf`;
        enlace.click();
        setTimeout(() => URL.revokeObjectURL(enlace.href), 10_000);
        this.generandoPdf.set(false);
      },
      error: () => {
        this.errorPdf.set('No fue posible generar el PDF.');
        this.generandoPdf.set(false);
      },
    });
  }

  protected formato(v: number | null, decimales = 1): string {
    return v === null ? '—' : new Intl.NumberFormat('es-CL', { maximumFractionDigits: decimales }).format(v);
  }
}
