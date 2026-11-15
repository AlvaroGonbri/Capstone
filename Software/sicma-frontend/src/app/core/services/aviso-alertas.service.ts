import { HttpClient } from '@angular/common/http';
import { Injectable, effect, inject, signal, untracked } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Alerta } from '../models';
import { AuthService } from './auth.service';
import { EstadoGeneralService } from './estado-general.service';

/** Cada cuánto se buscan alertas nuevas. La respuesta normal es una lista vacía. */
const INTERVALO_MS = 10_000;
const CLAVE_ULTIMA = 'sicma.aviso-alertas.ultima.';

/**
 * Aviso emergente de alertas nuevas (IoT, Zabbix o biometría) para quien está usando SICMA.
 *
 * - Al iniciar sesión no avisa de las alertas que ya estaban abiertas: esas se ven en el Panel y en
 *   los contadores del menú. Avisa de las que se abren después.
 * - Consulta cada 10 s solo con la pestaña visible. Al volver a la pestaña consulta de inmediato y
 *   avisa de todo lo que llegó mientras no se veía.
 * - Recuerda la última alerta avisada durante la sesión de la pestaña: recargar la página no hace
 *   perder las que se abrieron justo entonces.
 */
@Injectable({ providedIn: 'root' })
export class AvisoAlertasService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly estado = inject(EstadoGeneralService);

  /** Alertas por avisar, la más reciente primero. Vacía = aviso cerrado. */
  readonly nuevas = signal<Alerta[]>([]);

  private temporizador: ReturnType<typeof setInterval> | null = null;
  private usuarioId: number | null = null;
  /** Id de la última alerta conocida; null mientras no se toma la línea base. */
  private ultima: number | null = null;
  private consultando = false;

  constructor() {
    effect(() => {
      const usuario = this.auth.usuario();
      // El Departamento de contratistas no ve alertas.
      const activo = this.auth.autenticado() && !!usuario && !this.auth.tieneRol('contratistas');
      untracked(() => (activo ? this.iniciar(usuario!.id) : this.detener()));
    });
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.temporizador) {
        this.revisar();
      }
    });
  }

  /** Cierra el aviso. Las alertas siguen abiertas en el Panel, Monitoreo y Activos. */
  descartar(): void {
    this.nuevas.set([]);
  }

  /** Reemplaza una alerta del aviso por su versión actualizada (p. ej. tras reconocerla). */
  actualizar(alerta: Alerta): void {
    this.nuevas.update((lista) => lista.map((a) => (a.id === alerta.id ? alerta : a)));
    this.estado.refrescar();
  }

  private iniciar(usuarioId: number): void {
    if (this.temporizador && this.usuarioId === usuarioId) {
      return;
    }
    this.detener();
    this.usuarioId = usuarioId;
    this.ultima = this.leerUltima();
    this.revisar();
    this.temporizador = setInterval(() => {
      if (!document.hidden) {
        this.revisar();
      }
    }, INTERVALO_MS);
  }

  private detener(): void {
    if (this.temporizador) {
      clearInterval(this.temporizador);
      this.temporizador = null;
    }
    this.usuarioId = null;
    this.ultima = null;
    this.consultando = false;
    this.nuevas.set([]);
  }

  private revisar(): void {
    if (this.consultando || environment.usarDatosSimulados) {
      return;
    }
    this.consultando = true;
    const usuario = this.usuarioId;
    const lineaBase = this.ultima === null;
    const params: Record<string, string> = lineaBase ? {} : { despues_de: String(this.ultima) };
    this.http.get<Alerta[]>(`${environment.apiUrl}/alertas/`, { params }).subscribe({
      next: (alertas) => {
        this.consultando = false;
        if (usuario !== this.usuarioId) {
          return; // respuesta de una sesión anterior
        }
        const anterior = this.ultima ?? 0;
        this.guardarUltima(alertas.reduce((m, a) => Math.max(m, a.id), anterior));
        if (lineaBase) {
          return;
        }
        // También se filtra aquí: una API sin el filtro despues_de devolvería todas las abiertas.
        const conocidas = new Set(this.nuevas().map((a) => a.id));
        const recientes = alertas.filter((a) => a.id > anterior && !conocidas.has(a.id)).sort((a, b) => b.id - a.id);
        if (recientes.length === 0) {
          return;
        }
        this.nuevas.update((lista) => [...recientes, ...lista]);
        this.estado.refrescar();
      },
      // Sin conexión o sesión vencida: se reintenta en el próximo ciclo, sin avisar nada.
      error: () => (this.consultando = false),
    });
  }

  private leerUltima(): number | null {
    try {
      const valor = sessionStorage.getItem(CLAVE_ULTIMA + this.usuarioId);
      return valor === null || !/^\d+$/.test(valor) ? null : Number(valor);
    } catch {
      return null;
    }
  }

  private guardarUltima(id: number): void {
    this.ultima = id;
    try {
      sessionStorage.setItem(CLAVE_ULTIMA + this.usuarioId, String(id));
    } catch {
      // Sin almacenamiento (modo privado estricto): solo se pierde el aviso de lo que llegue al recargar.
    }
  }
}
