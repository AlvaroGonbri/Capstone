import { Pipe, PipeTransform } from '@angular/core';
import { NivelAmbiental } from '../core/models';

/** Traduce el nivel ambiental al color de Ionic que le corresponde. */
@Pipe({ name: 'colorNivel' })
export class ColorNivelPipe implements PipeTransform {
  transform(nivel: NivelAmbiental): string {
    switch (nivel) {
      case 'critico':
        return 'danger';
      case 'advertencia':
        return 'warning';
      default:
        return 'success';
    }
  }
}
