"""Base de los comandos que SICMA ejecuta cada cierto tiempo (Zabbix, buzón de intervenciones).

Cada comando corre como un proceso aparte del servidor web:
    python manage.py <comando>             # queda corriendo, una pasada cada `intervalo` segundos
    python manage.py <comando> --una-vez   # una sola pasada (para el Programador de tareas)
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone


class ComandoPeriodico(BaseCommand):
    intervalo_por_defecto = 60
    descripcion_tarea = 'la tarea'

    def add_arguments(self, parser):
        parser.add_argument('--una-vez', action='store_true', help='Hace una sola pasada y termina.')
        parser.add_argument(
            '--intervalo', type=int, default=self.intervalo_por_defecto,
            help=f'Segundos entre pasadas (por defecto {self.intervalo_por_defecto}).',
        )

    def pasada(self) -> str:
        """Ejecuta una pasada y devuelve el texto que se imprime. Lanza excepción si falla."""
        raise NotImplementedError

    def handle(self, *args, una_vez=False, intervalo=None, **options):
        intervalo = intervalo or self.intervalo_por_defecto
        if intervalo < 10:
            self.stderr.write('El intervalo mínimo es 10 segundos.')
            return
        # El correo asíncrono sale en un hilo daemon que muere si el proceso termina (--una-vez
        # o Ctrl+C) antes de enviarlo. Este proceso no atiende peticiones: puede enviar en línea.
        asincrono = getattr(settings, 'ALERTAS_CORREO_ASINCRONO', True)
        settings.ALERTAS_CORREO_ASINCRONO = False
        try:
            self._ejecutar(una_vez, intervalo)
        finally:
            settings.ALERTAS_CORREO_ASINCRONO = asincrono

    def _ejecutar(self, una_vez, intervalo):
        if una_vez:
            self._pasada_con_registro()
            return

        self.stdout.write(f'Ejecutando {self.descripcion_tarea} cada {intervalo} s. Ctrl+C para detener.')
        try:
            while True:
                inicio = time.monotonic()
                close_old_connections()  # el proceso vive mucho: evita conexiones MySQL caducadas
                try:
                    self._pasada_con_registro()
                except Exception as error:  # una falla puntual no debe detener el proceso
                    self.stderr.write(f'{timezone.localtime():%H:%M:%S} error inesperado: {error}')
                time.sleep(max(0.0, intervalo - (time.monotonic() - inicio)))
        except KeyboardInterrupt:
            self.stdout.write('Proceso detenido.')

    def _pasada_con_registro(self):
        texto = self.pasada()
        if texto:
            self.stdout.write(f'{timezone.localtime():%H:%M:%S} {texto}')
