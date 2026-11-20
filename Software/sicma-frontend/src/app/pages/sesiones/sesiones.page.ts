import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  IonBadge,
  IonButton,
  IonContent,
  IonIcon,
  IonSearchbar,
  IonSegment,
  IonSegmentButton,
  IonLabel,
  IonSpinner,
  IonText,
} from '@ionic/angular';
import { addIcons } from 'ionicons';
import { desktopOutline, phonePortraitOutline } from 'ionicons/icons';
import { SesionActiva } from '../../core/models';
import { claseRol, etiquetaRol } from '../../core/services/roles.util';
import { SesionesService } from '../../core/services/sesiones.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { HacePipe } from '../../shared/hace.pipe';
import { mensajeErrorApi } from '../../core/services/inventario.service';

const REFRESCO_MS = 30_000;
type FiltroCanal = 'todos' | 'web' | 'movil';

/** Sesiones activas (web y app móvil) con la opción de cerrarlas. Administrador y Privilegiado. */
@Component({
  selector: 'app-sesiones',
  imports: [
    DatePipe,
    FormsModule,
    EncabezadoComponent,
    HacePipe,
    IonBadge,
    IonButton,
    IonContent,
    IonIcon,
    IonLabel,
    IonSearchbar,
    IonSegment,
    IonSegmentButton,
    IonSpinner,
    IonText,
  ],
  templateUrl: './sesiones.page.html',
  styleUrl: './sesiones.page.scss',
})
export class SesionesPage {
  private readonly servicio = inject(SesionesService);

  protected readonly etiquetaRol = etiquetaRol;
  protected readonly claseRol = claseRol;

  protected readonly sesiones = signal<SesionActiva[]>([]);
  protected readonly cargando = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly mensaje = signal<string | null>(null);
  protected readonly revocando = signal<string | null>(null);
  protected readonly busqueda = signal('');
  protected readonly canal = signal<FiltroCanal>('todos');
  /** Hora de referencia para la duración; avanza con cada recarga. */
  private readonly ahora = signal(Date.now());

  protected readonly visibles = computed(() => {
    const texto = this.busqueda().trim().toLowerCase();
    return this.sesiones().filter(
      (s) =>
        (this.canal() === 'todos' || s.canal === this.canal()) &&
        (!texto || [s.nombre, s.username, s.ip, s.dispositivo, etiquetaRol(s.rol)].some((v) => (v ?? '').toLowerCase().includes(texto))),
    );
  });

  protected readonly resumen = computed(() => {
    const lista = this.sesiones();
    return {
      total: lista.length,
      usuarios: new Set(lista.map((s) => s.usuario_id)).size,
      movil: lista.filter((s) => s.canal === 'movil').length,
    };
  });

  /** Sesiones de cada usuario (sin contar la propia actual): para el botón "todas". */
  private readonly porUsuario = computed(() => {
    const conteo = new Map<number, number>();
    for (const s of this.sesiones()) {
      if (!s.actual) {
        conteo.set(s.usuario_id, (conteo.get(s.usuario_id) ?? 0) + 1);
      }
    }
    return conteo;
  });

  constructor() {
    addIcons({ desktopOutline, phonePortraitOutline });
    const temporizador = setInterval(() => {
      if (!document.hidden) {
        this.cargar();
      }
    }, REFRESCO_MS);
    inject(DestroyRef).onDestroy(() => clearInterval(temporizador));
  }

  /** Cada vez que se muestra la pantalla (también al volver a ella desde el menú). */
  ionViewWillEnter(): void {
    this.cargar();
  }

  protected cargar(): void {
    this.servicio.listar().subscribe({
      next: (lista) => {
        this.sesiones.set(lista);
        this.ahora.set(Date.now());
        this.cargando.set(false);
        this.error.set(null);
      },
      error: (r) => {
        this.cargando.set(false);
        this.error.set(mensajeErrorApi(r.error, 'No fue posible consultar las sesiones.'));
      },
    });
  }

  protected duracion(s: SesionActiva): string {
    const minutos = Math.max(0, Math.round((this.ahora() - new Date(s.inicio).getTime()) / 60_000));
    if (minutos < 60) {
      return `${minutos} min`;
    }
    const horas = Math.floor(minutos / 60);
    return horas < 24 ? `${horas} h ${String(minutos % 60).padStart(2, '0')} min` : `${Math.floor(horas / 24)} d ${horas % 24} h`;
  }

  protected otrasDelUsuario(s: SesionActiva): number {
    return this.porUsuario().get(s.usuario_id) ?? 0;
  }

  protected revocar(s: SesionActiva): void {
    const donde = s.canal === 'movil' ? 'la app móvil' : 'la web';
    if (!confirm(`¿Cerrar la sesión de ${s.nombre} en ${donde}${s.dispositivo ? ` (${s.dispositivo})` : ''}?\n\n` +
      'Saldrá en su siguiente acción y tendrá que volver a iniciar sesión.')) {
      return;
    }
    this.ejecutar(s.id, this.servicio.revocar(s.id), `Se cerró la sesión de ${s.nombre}.`);
  }

  protected revocarTodas(s: SesionActiva): void {
    const n = this.otrasDelUsuario(s);
    if (!confirm(`¿Cerrar las ${n} sesiones de ${s.nombre}, en la web y en la app?`)) {
      return;
    }
    this.ejecutar(s.id, this.servicio.revocarUsuario(s.usuario_id), `Se cerraron las sesiones de ${s.nombre}.`);
  }

  private ejecutar(id: string, operacion: ReturnType<SesionesService['revocar']>, exito: string): void {
    this.revocando.set(id);
    this.mensaje.set(null);
    this.error.set(null);
    operacion.subscribe({
      next: () => {
        this.revocando.set(null);
        this.mensaje.set(exito);
        this.cargar();
      },
      error: (r) => {
        this.revocando.set(null);
        this.error.set(mensajeErrorApi(r.error, 'No fue posible cerrar la sesión.'));
        this.cargar();
      },
    });
  }
}
