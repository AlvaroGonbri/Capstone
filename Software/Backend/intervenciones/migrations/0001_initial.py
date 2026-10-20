"""Intervenciones: ampliación aditiva del esquema del equipo.

Cambios en tablas del script SQL (actualizar SICMA-BDD):
  - intervencion.responsable_id pasa a NULL (el técnico se asigna después de la aprobación)
  - intervencion.estado agrega 'Rechazada' al enum
  - intervencion: solicitante_nombre, solicitante_correo, rack, origen_externo_id (UNIQUE),
    fecha_solicitud, fecha_cierre, observacion_cierre
  - decision_intervencion.decisor_id pasa a NULL y se agrega decisor_correo
    (el decisor aprueba en Teams y puede no tener cuenta en SICMA)
Igual que en inventario/0001, se aplica solo en MySQL y solo lo que falta.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ESTADOS = "'Pendiente','CambiosSolicitados','Aprobada','Rechazada','EnEjecucion','Ejecutada','Fallida','Cancelada'"

COLUMNAS_INTERVENCION = (
    ('solicitante_nombre', 'VARCHAR(200) NULL'),
    ('solicitante_correo', 'VARCHAR(254) NULL'),
    ('rack', 'VARCHAR(200) NULL'),
    ('origen_externo_id', 'VARCHAR(100) NULL'),
    ('fecha_solicitud', "DATETIME NULL COMMENT 'UTC (RNF-INT-02)'"),
    ('fecha_cierre', "DATETIME NULL COMMENT 'UTC (RNF-INT-02)'"),
    ('observacion_cierre', 'TEXT NULL'),
)


def _columnas(schema_editor, tabla):
    conexion = schema_editor.connection
    if conexion.vendor != 'mysql' or tabla not in conexion.introspection.table_names():
        return None
    with conexion.cursor() as cursor:
        return {c.name: c for c in conexion.introspection.get_table_description(cursor, tabla)}


def _indices(schema_editor, tabla):
    with schema_editor.connection.cursor() as cursor:
        return set(schema_editor.connection.introspection.get_constraints(cursor, tabla))


def ampliar_esquema(apps, schema_editor):
    columnas = _columnas(schema_editor, 'intervencion')
    if columnas is not None:
        cambios = [
            'MODIFY responsable_id INT NULL',
            f"MODIFY estado ENUM({ESTADOS}) NOT NULL DEFAULT 'Pendiente'",
        ]
        cambios += [f'ADD COLUMN {nombre} {tipo}' for nombre, tipo in COLUMNAS_INTERVENCION if nombre not in columnas]
        schema_editor.execute('ALTER TABLE intervencion ' + ', '.join(cambios))
        if 'uq_intervencion_origen' not in _indices(schema_editor, 'intervencion'):
            schema_editor.execute('ALTER TABLE intervencion ADD UNIQUE KEY uq_intervencion_origen (origen_externo_id)')

    columnas = _columnas(schema_editor, 'decision_intervencion')
    if columnas is not None:
        cambios = ['MODIFY decisor_id INT NULL']
        if 'decisor_correo' not in columnas:
            cambios.append('ADD COLUMN decisor_correo VARCHAR(254) NULL')
        schema_editor.execute('ALTER TABLE decision_intervencion ' + ', '.join(cambios))


class Migration(migrations.Migration):

    initial = True
    # MySQL no puede revertir DDL dentro de una transacción; Django exige ejecutarla sin atomic.
    atomic = False

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventario', '0002_estadoactivo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Intervencion',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('objetivo', models.CharField(max_length=500)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('impacto_esperado', models.TextField(blank=True, null=True)),
                ('fecha_inicio', models.DateTimeField(blank=True, null=True)),
                ('fecha_termino', models.DateTimeField(blank=True, null=True)),
                ('plan_reversa', models.TextField(blank=True, null=True)),
                ('estado', models.CharField(default='Pendiente', max_length=18)),
                ('solicitante_nombre', models.CharField(blank=True, max_length=200, null=True)),
                ('solicitante_correo', models.CharField(blank=True, max_length=254, null=True)),
                ('rack', models.CharField(blank=True, max_length=200, null=True)),
                ('origen_externo_id', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('fecha_solicitud', models.DateTimeField(blank=True, null=True)),
                ('fecha_cierre', models.DateTimeField(blank=True, null=True)),
                ('observacion_cierre', models.TextField(blank=True, null=True)),
                ('responsable', models.ForeignKey(blank=True, db_column='responsable_id', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='intervenciones_asignadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'intervencion', 'managed': False},
        ),
        migrations.CreateModel(
            name='DecisionIntervencion',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('decisor_correo', models.CharField(blank=True, max_length=254, null=True)),
                ('decision', models.CharField(max_length=18)),
                ('observacion', models.TextField(blank=True, null=True)),
                ('fecha_hora', models.DateTimeField()),
                ('decisor', models.ForeignKey(blank=True, db_column='decisor_id', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('intervencion', models.ForeignKey(db_column='intervencion_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='decisiones', to='intervenciones.intervencion')),
            ],
            options={'db_table': 'decision_intervencion', 'managed': False},
        ),
        migrations.CreateModel(
            name='IntervencionActivo',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('estado_final_activo', models.CharField(blank=True, max_length=100, null=True)),
                ('activo', models.ForeignKey(db_column='activo_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='intervenciones', to='inventario.activo')),
                ('intervencion', models.ForeignKey(db_column='intervencion_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='activos_afectados', to='intervenciones.intervencion')),
            ],
            options={'db_table': 'intervencion_activo', 'managed': False, 'unique_together': {('intervencion', 'activo')}},
        ),
        migrations.RunPython(ampliar_esquema, migrations.RunPython.noop),
    ]
