import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonContent,
  IonInput,
  IonItem,
  IonLabel,
  IonNote,
  IonSpinner,
} from '@ionic/angular';
import { Arduino } from '../../core/models';
import { AuthService } from '../../core/services/auth.service';
import { ArduinosService } from '../../core/services/arduinos.service';
import { EncabezadoComponent } from '../../shared/encabezado.component';

@Component({
  selector: 'app-arduinos',
  imports: [
    DatePipe,
    EncabezadoComponent,
    IonBadge,
    IonButton,
    IonCard,
    IonCardContent,
    IonCardHeader,
    IonCardTitle,
    IonContent,
    IonInput,
    IonItem,
    IonLabel,
    IonNote,
    IonSpinner,
  ],
  templateUrl: './arduinos.page.html',
  styleUrl: './arduinos.page.scss',
})
export class ArduinosPage {
  private readonly servicio = inject(ArduinosService);
  private readonly auth = inject(AuthService);

  protected readonly cargando = signal(true);
  protected readonly arduinos = signal<Arduino[]>([]);
  protected readonly guardando = signal<string | null>(null);
  protected readonly mensaje = signal<string | null>(null);
  protected readonly soloConsulta = this.auth.usuario()?.rol === 'auditor';

  constructor() {
    this.servicio.listar().subscribe((lista) => {
      this.arduinos.set(lista);
      this.cargando.set(false);
    });
  }

  protected guardar(arduino: Arduino): void {
    if (
      arduino.temperaturaMinima >= arduino.temperaturaAdvertencia ||
      arduino.temperaturaAdvertencia >= arduino.temperaturaCritica
    ) {
      this.mensaje.set('Los parámetros deben cumplir: mínima < advertencia < crítica.');
      return;
    }

    this.guardando.set(arduino.id);
    this.mensaje.set(null);
    this.servicio.actualizarParametros(arduino.id, arduino).subscribe({
      next: (actualizado) => {
        this.arduinos.update((lista) =>
          lista.map((item) => (item.id === actualizado.id ? actualizado : item)),
        );
        this.guardando.set(null);
        this.mensaje.set(`Parámetros guardados para ${arduino.nombre}.`);
      },
      error: (error: Error) => {
        this.guardando.set(null);
        this.mensaje.set(error.message);
      },
    });
  }

  protected actualizarParametro(
    arduino: Arduino,
    parametro: 'temperaturaMinima' | 'temperaturaAdvertencia' | 'temperaturaCritica',
    valor: string | number | null | undefined,
  ): void {
    const numero = Number(valor);
    if (!Number.isFinite(numero)) {
      return;
    }
    this.arduinos.update((lista) =>
      lista.map((item) => (item.id === arduino.id ? { ...item, [parametro]: numero } : item)),
    );
  }
}
