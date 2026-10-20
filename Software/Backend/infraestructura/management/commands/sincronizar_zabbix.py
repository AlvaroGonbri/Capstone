"""Consulta Zabbix cada minuto (RF-INF-01).

Uso:
    python manage.py sincronizar_zabbix              # queda corriendo, una pasada cada 60 s
    python manage.py sincronizar_zabbix --una-vez    # una sola pasada (para el Programador de tareas)

Se ejecuta como un proceso aparte del servidor web, de modo que el estado de los servidores
se actualiza aunque nadie tenga el frontend abierto.
"""
from backendsicma.comando_periodico import ComandoPeriodico
from infraestructura.sincronizacion import INTERVALO_SEGUNDOS, sincronizar


class Command(ComandoPeriodico):
    help = 'Consulta a Zabbix el estado de los servidores cada minuto y concilia sus problemas (RF-INF-01).'
    intervalo_por_defecto = INTERVALO_SEGUNDOS
    descripcion_tarea = 'la sincronización con Zabbix'

    def pasada(self):
        resultado = sincronizar()
        if not resultado['exitosa']:
            self.stderr.write(f"Zabbix no respondió: {resultado['error']}")
            return ''
        return (
            f"OK: {resultado['hosts']} hosts, {resultado['problemas_abiertos']} problemas abiertos "
            f"({resultado['nuevos']} nuevos, {resultado['resueltos']} resueltos)."
        )
