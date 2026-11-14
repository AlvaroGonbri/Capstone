import { Pipe, PipeTransform } from '@angular/core';

/** Tiempo transcurrido en palabras: "hace 12 s", "hace 3 min", "hace 3 h", "hace 14 días". */
export function haceCuanto(fecha: string | Date | null | undefined, ahora = Date.now()): string {
  if (!fecha) {
    return '';
  }
  const ms = ahora - new Date(fecha).getTime();
  if (!Number.isFinite(ms)) {
    return '';
  }
  const segundos = Math.round(ms / 1000);
  if (segundos < 10) return 'hace un momento';
  if (segundos < 60) return `hace ${segundos} s`;
  const minutos = Math.floor(segundos / 60);
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  return dias === 1 ? 'hace 1 día' : `hace ${dias} días`;
}

/**
 * Hora relativa de un dato que puede quedar desactualizado (p. ej. la última lectura de un sensor).
 * Impuro: se recalcula en cada detección de cambios, así el texto avanza sin recargar la página.
 */
@Pipe({ name: 'hace', pure: false })
export class HacePipe implements PipeTransform {
  transform(fecha: string | Date | null | undefined): string {
    return haceCuanto(fecha);
  }
}
