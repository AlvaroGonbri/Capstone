"""Reportes: fecha de cierre de cada alerta, para calcular el tiempo de resolución.

Cambio en una tabla del script SQL (actualizar SICMA-BDD):
  - alerta.fecha_cierre DATETIME NULL
Igual que en accesos/0001, se aplica solo en MySQL y solo si falta. Las alertas cerradas a mano antes
de este cambio toman la fecha de su cierre en gestion_alerta; las cerradas automáticamente quedan vacías.
"""
from django.db import migrations, models


def agregar_columna(apps, schema_editor):
    conexion = schema_editor.connection
    if conexion.vendor != 'mysql' or 'alerta' not in conexion.introspection.table_names():
        return
    with conexion.cursor() as cursor:
        columnas = {c.name for c in conexion.introspection.get_table_description(cursor, 'alerta')}
    if 'fecha_cierre' not in columnas:
        schema_editor.execute(
            "ALTER TABLE alerta ADD COLUMN fecha_cierre DATETIME NULL "
            "COMMENT 'Cuándo se cerró (UTC); vacía en alertas cerradas antes de 2026-11'"
        )
    if 'gestion_alerta' in conexion.introspection.table_names():
        schema_editor.execute(
            "UPDATE alerta a JOIN ("
            "  SELECT alerta_id, MAX(fecha_hora) AS cierre FROM gestion_alerta"
            "  WHERE accion = 'Cerrada' GROUP BY alerta_id"
            ") g ON g.alerta_id = a.id "
            "SET a.fecha_cierre = g.cierre "
            "WHERE a.estado = 'Cerrada' AND a.fecha_cierre IS NULL"
        )


class Migration(migrations.Migration):

    # MySQL no puede revertir DDL dentro de una transacción.
    atomic = False

    dependencies = [
        ('alertas', '0003_gestion_alerta'),
    ]

    operations = [
        migrations.AddField(
            model_name='alerta',
            name='fecha_cierre',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(agregar_columna, migrations.RunPython.noop),
    ]
