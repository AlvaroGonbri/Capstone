"""Lee cada minuto el buzón de SICMA y aplica los avisos del flujo de Power Automate (RF-INT-01 a 03).

Uso:
    python manage.py procesar_intervenciones              # queda corriendo, una pasada cada 60 s
    python manage.py procesar_intervenciones --una-vez    # una sola pasada
"""
from backendsicma.comando_periodico import ComandoPeriodico
from intervenciones.buzon import leer_buzon


class Command(ComandoPeriodico):
    help = 'Lee el buzón de SICMA y registra las solicitudes y decisiones que envía Power Automate.'
    descripcion_tarea = 'la lectura del buzón de intervenciones'

    def pasada(self):
        procesados, descartados = leer_buzon()
        for detalle in descartados:
            self.stderr.write(f'Descartado: {detalle}')
        if not procesados and not descartados:
            return 'Buzón sin correos nuevos.'
        resumen = ', '.join(
            f"{r.tipo} #{r.intervencion_id}{'' if r.nueva else ' (repetido)'}" for r in procesados
        )
        return f'{len(procesados)} procesados, {len(descartados)} descartados. {resumen}'.strip()
