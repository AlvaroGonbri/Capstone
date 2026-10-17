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

/** Texto corto del rango, p. ej. "18–27 °C" o "sin definir". */
export function rangoTexto(minimo: number | null, maximo: number | null, unidad: string): string {
  if (minimo === null && maximo === null) {
    return 'sin definir';
  }
  return `${minimo ?? '—'}–${maximo ?? '—'} ${unidad}`;
}
