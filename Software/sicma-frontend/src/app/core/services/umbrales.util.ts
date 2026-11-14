import { NivelAmbiental, Umbrales } from '../models';

/**
 * Compara una lectura con los umbrales de su zona (RF-AMB-03).
 * Fuera del rango mínimo–máximo de cualquier variable = 'critico'.
 * Si la zona no tiene umbrales, la lectura no se puede evaluar y queda 'normal'.
 */
export function evaluarLectura(
  temperatura: number,
  humedad: number,
  umbrales: Umbrales | null,
): { nivel: NivelAmbiental; motivos: string[] } {
  const motivos: string[] = [];
  if (umbrales) {
    if (umbrales.temperaturaMinima !== null && temperatura < umbrales.temperaturaMinima) {
      motivos.push(`temperatura bajo ${umbrales.temperaturaMinima} °C`);
    }
    if (umbrales.temperaturaMaxima !== null && temperatura > umbrales.temperaturaMaxima) {
      motivos.push(`temperatura sobre ${umbrales.temperaturaMaxima} °C`);
    }
    if (umbrales.humedadMinima !== null && humedad < umbrales.humedadMinima) {
      motivos.push(`humedad bajo ${umbrales.humedadMinima} %`);
    }
    if (umbrales.humedadMaxima !== null && humedad > umbrales.humedadMaxima) {
      motivos.push(`humedad sobre ${umbrales.humedadMaxima} %`);
    }
  }
  return { nivel: motivos.length ? 'critico' : 'normal', motivos };
}

/**
 * Posición (en %) del rango permitido y de la lectura dentro de una barra.
 * Solo es presentación: usa los mismos umbrales con que ya se evalúa el sensor.
 */
export function posicionesBarra(valor: number, minimo: number | null, maximo: number | null) {
  if (minimo === null || maximo === null) {
    return null;
  }
  const margen = Math.max((maximo - minimo) * 0.8, 1);
  const desde = Math.min(minimo - margen, valor - 1);
  const hasta = Math.max(maximo + margen, valor + 1);
  const pos = (v: number) => ((v - desde) / (hasta - desde)) * 100;
  return { inicio: pos(minimo), fin: pos(maximo), marca: pos(valor) };
}

/** 'sobre' o 'bajo' si la lectura sale del rango; null si está dentro o no hay rango. */
export function respectoDelRango(valor: number, minimo: number | null, maximo: number | null): 'sobre' | 'bajo' | null {
  if (maximo !== null && valor > maximo) return 'sobre';
  if (minimo !== null && valor < minimo) return 'bajo';
  return null;
}

/** Texto corto del rango, p. ej. "18–27 °C" o "sin definir". */
export function rangoTexto(minimo: number | null, maximo: number | null, unidad: string): string {
  if (minimo === null && maximo === null) {
    return 'sin definir';
  }
  return `${minimo ?? '—'}–${maximo ?? '—'} ${unidad}`;
}
