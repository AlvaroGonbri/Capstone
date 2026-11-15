import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { IonButton, IonCard, IonCheckbox, IonContent, IonInput, IonNote, IonSpinner } from '@ionic/angular';
import { interval } from 'rxjs';
import {
  EstadoIntegraciones,
  NombrePrueba,
  NombreSecreto,
  ResultadoPrueba,
  SecretoRenovado,
} from '../../core/models';
import { IntegracionesService } from '../../core/services/integraciones.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';
import { HacePipe } from '../../shared/hace.pipe';
import { copiarTexto } from '../../shared/texto.util';

type Nivel = 'ok' | 'advertencia' | 'error' | 'neutro';

interface Indicador {
  nivel: Nivel;
  texto: string;
}

interface SecretoVista {
  titulo: string;
  corto: string;
  destino: string;
  /** Qué deja de funcionar mientras el valor nuevo no esté pegado en el otro lado. */
  efecto: string;
  pasos: string[];
  ajuste: string;
}

/** Los dos secretos que genera SICMA y dónde hay que pegarlos después de renovarlos. */
const SECRETOS: Record<NombreSecreto, SecretoVista> = {
  zabbix_webhook: {
    titulo: 'secreto del webhook de Zabbix',
    corto: 'Webhook de Zabbix',
    destino: 'Zabbix',
    efecto: 'Zabbix no podrá avisar al instante de los problemas (la consulta de cada minuto sigue funcionando)',
    pasos: [
      'En Zabbix, abre Alerts › Media types › el webhook de SICMA.',
      'Reemplaza el valor del parámetro que se envía en la cabecera X-Zabbix-Token y guarda.',
      'Usa el botón Test del tipo de medio: SICMA debe responder 202 (o 400 si el evento de prueba está incompleto, pero no 403).',
    ],
    ajuste: 'ZABBIX_WEBHOOK_SECRET',
  },
  intervenciones_flujo: {
    titulo: 'token del flujo de Power Automate',
    corto: 'Flujo de Power Automate',
    destino: 'el flujo de Power Automate',
    efecto: 'SICMA descartará los correos del flujo (solicitudes y decisiones de intervenciones)',
    pasos: [
      'En Power Automate, abre el flujo de intervenciones y edítalo.',
      'En cada acción que envía un correo a SICMA (solicitud nueva y decisión), reemplaza el valor del campo "token" del JSON.',
      'Guarda el flujo. La próxima solicitud debe aparecer en Intervenciones y aquí, como último correo aceptado.',
    ],
    ajuste: 'INTERVENCIONES_TOKEN',
  },
};

const PRUEBAS: NombrePrueba[] = ['zabbix', 'correo', 'tunel', 'gemini'];
const REFRESCO_MS = 30_000;

function reciente(fecha: string | null | undefined, horas = 24): boolean {
  return !!fecha && Date.now() - new Date(fecha).getTime() < horas * 3600_000;
}

function segunPrueba(prueba: ResultadoPrueba | undefined): Indicador | null {
  if (!prueba) return null;
  return prueba.ok ? { nivel: 'ok', texto: 'Funciona' } : { nivel: 'error', texto: 'Falla' };
}

@Component({
  selector: 'app-integraciones',
  imports: [
    DatePipe,
    NgTemplateOutlet,
    ReactiveFormsModule,
    RouterLink,
    EncabezadoComponent,
    HacePipe,
    IonButton,
    IonCard,
    IonCheckbox,
    IonContent,
    IonInput,
    IonNote,
    IonSpinner,
  ],
  templateUrl: './integraciones.page.html',
  styleUrl: './integraciones.page.scss',
})
export class IntegracionesPage {
  private readonly servicio = inject(IntegracionesService);

  protected readonly estado = signal<EstadoIntegraciones | null>(null);
  protected readonly cargando = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly pruebas = signal<Partial<Record<NombrePrueba, ResultadoPrueba>>>({});
  protected readonly probando = signal<Partial<Record<NombrePrueba, boolean>>>({});

  // Renovación: un panel dentro de la tarjeta del secreto (uno a la vez).
  protected readonly renovando = signal<NombreSecreto | null>(null);
  protected readonly enviando = signal(false);
  protected readonly errorRenovacion = signal<string | null>(null);
  /** El valor nuevo vive solo aquí, hasta cerrar el panel o salir de la página. */
  protected readonly renovado = signal<SecretoRenovado | null>(null);
  protected readonly copiado = signal(false);
  protected readonly formRenovar = new FormGroup({
    password: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    inmediato: new FormControl(false, { nonNullable: true }),
  });

  /** Estado resumido de cada integración: color + texto (nunca solo color). */
  protected readonly indicadores = computed(() => {
    const e = this.estado();
    if (!e) return null;
    const p = this.pruebas();
    return {
      zabbix: this.indicadorZabbix(e, p.zabbix),
      webhook: this.indicadorWebhook(e),
      correo: this.indicadorCorreo(e, p.correo),
      buzon: this.indicadorBuzon(e),
      tunel: this.indicadorTunel(e, p.tunel),
      gemini: this.indicadorGemini(e, p.gemini),
    };
  });

  constructor() {
    this.cargar();
    interval(REFRESCO_MS).pipe(takeUntilDestroyed()).subscribe(() => this.cargar(true));
    // Al salir de la página no queda ningún secreto en memoria.
    inject(DestroyRef).onDestroy(() => this.cerrarRenovacion());
  }

  protected cargar(silencioso = false): void {
    if (!silencioso) this.cargando.set(true);
    this.servicio.estado().subscribe({
      next: (estado) => {
        this.estado.set(estado);
        this.error.set(null);
        this.cargando.set(false);
      },
      error: (e: HttpErrorResponse) => {
        if (!silencioso || !this.estado()) {
          this.error.set(e.error?.detail ?? 'No fue posible cargar el estado de las integraciones.');
        }
        this.cargando.set(false);
      },
    });
  }

  protected probar(nombre: NombrePrueba): void {
    this.probando.update((p) => ({ ...p, [nombre]: true }));
    const guardar = (resultado: ResultadoPrueba) => {
      this.pruebas.update((p) => ({ ...p, [nombre]: resultado }));
      this.probando.update((p) => ({ ...p, [nombre]: false }));
    };
    this.servicio.probar(nombre).subscribe({
      next: guardar,
      error: (e: HttpErrorResponse) =>
        guardar({
          ok: false,
          detalle:
            e.status === 429
              ? 'Demasiadas pruebas seguidas: espera un minuto.'
              : (e.error?.detail ?? 'No fue posible hacer la prueba.'),
          probado_en: new Date().toISOString(),
        }),
    });
  }

  protected probarTodo(): void {
    PRUEBAS.forEach((nombre) => this.probar(nombre));
  }

  protected abrirRenovacion(nombre: NombreSecreto): void {
    this.cerrarRenovacion();
    this.renovando.set(nombre);
  }

  protected cerrarRenovacion(): void {
    this.renovando.set(null);
    this.renovado.set(null);
    this.errorRenovacion.set(null);
    this.copiado.set(false);
    this.formRenovar.reset();
  }

  protected confirmarRenovacion(): void {
    const nombre = this.renovando();
    if (!nombre || this.formRenovar.invalid || this.enviando()) return;
    const { password, inmediato } = this.formRenovar.getRawValue();
    this.formRenovar.controls.password.reset(); // la contraseña no queda en el formulario
    this.enviando.set(true);
    this.errorRenovacion.set(null);
    this.servicio.renovar(nombre, password, inmediato).subscribe({
      next: (resultado) => {
        this.renovado.set(resultado);
        this.enviando.set(false);
        this.cargar(true);
      },
      error: (e: HttpErrorResponse) => {
        this.errorRenovacion.set(this.mensajeRenovacion(e));
        this.enviando.set(false);
      },
    });
  }

  protected async copiar(texto: string): Promise<void> {
    this.copiado.set(await copiarTexto(texto));
  }

  protected nombreSecreto(nombre: NombreSecreto): string {
    return SECRETOS[nombre]?.corto ?? nombre;
  }

  protected vistaDe(nombre: NombreSecreto): SecretoVista {
    return SECRETOS[nombre];
  }

  protected resultadoDe(nombre: NombrePrueba): ResultadoPrueba | undefined {
    return this.pruebas()[nombre];
  }

  protected estaProbando(nombre: NombrePrueba): boolean {
    return !!this.probando()[nombre];
  }

  private mensajeRenovacion(e: HttpErrorResponse): string {
    if (e.status === 429) return 'Demasiados intentos. Espera un momento antes de volver a intentarlo.';
    if (e.error?.detail) return e.error.detail;
    if (e.status === 404 || e.status === 0) return 'La renovación solo está disponible desde la red local.';
    return 'No fue posible renovar el secreto.';
  }

  // ------------------------------------------------------------ Indicadores

  private indicadorZabbix(e: EstadoIntegraciones, prueba?: ResultadoPrueba): Indicador {
    if (!e.zabbix.configurado) return { nivel: 'neutro', texto: 'Sin configurar' };
    const segun = segunPrueba(prueba);
    if (segun) return segun;
    if (e.zabbix.al_dia) return { nivel: 'ok', texto: 'Funciona' };
    if (e.zabbix.error) return { nivel: 'error', texto: 'Falla' };
    return { nivel: 'advertencia', texto: 'Sin datos recientes' };
  }

  private indicadorWebhook(e: EstadoIntegraciones): Indicador {
    if (!e.webhook.secreto.configurado) return { nivel: 'neutro', texto: 'Sin configurar' };
    if (reciente(e.webhook.ultimo_rechazo)) return { nivel: 'advertencia', texto: 'Rechazos recientes' };
    return { nivel: 'ok', texto: 'Configurado' };
  }

  private indicadorCorreo(e: EstadoIntegraciones, prueba?: ResultadoPrueba): Indicador {
    if (!e.correo.configurado) return { nivel: 'neutro', texto: 'Sin configurar' };
    const segun = segunPrueba(prueba);
    if (segun) return segun;
    // Si el buzón se está leyendo sin errores, la cuenta y la contraseña funcionan.
    const proceso = e.buzon.proceso;
    if (e.buzon.configurado && proceso.activo && !proceso.error) return { nivel: 'ok', texto: 'Funciona' };
    return { nivel: 'neutro', texto: 'Sin probar' };
  }

  private indicadorBuzon(e: EstadoIntegraciones): Indicador {
    if (!e.buzon.configurado) return { nivel: 'neutro', texto: 'Sin configurar' };
    if (!e.buzon.proceso.activo) return { nivel: 'error', texto: 'Proceso detenido' };
    if (e.buzon.proceso.error) return { nivel: 'error', texto: 'Falla' };
    if (reciente(e.buzon.ultimo_descarte)) return { nivel: 'advertencia', texto: 'Correos descartados' };
    return { nivel: 'ok', texto: 'Funciona' };
  }

  private indicadorGemini(e: EstadoIntegraciones, prueba?: ResultadoPrueba): Indicador {
    if (!e.gemini.configurado) return { nivel: 'neutro', texto: 'Sin configurar' };
    const segun = segunPrueba(prueba);
    if (segun) return segun;
    if (e.gemini.error) return { nivel: 'advertencia', texto: 'Usando plantilla' };
    if (e.gemini.ultimo_resumen) return { nivel: 'ok', texto: 'Funciona' };
    return { nivel: 'neutro', texto: 'Sin probar' };
  }

  private indicadorTunel(e: EstadoIntegraciones, prueba?: ResultadoPrueba): Indicador {
    if (!e.tunel.host) return { nivel: 'neutro', texto: 'Sin configurar' };
    if (prueba && !prueba.ok && prueba.expuestas?.length) return { nivel: 'error', texto: 'Rutas expuestas' };
    return segunPrueba(prueba) ?? { nivel: 'neutro', texto: 'Sin probar' };
  }
}
