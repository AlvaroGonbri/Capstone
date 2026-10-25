"""Control de acceso físico: ampliación aditiva del esquema del equipo.

Cambios en tablas del script SQL (actualizar SICMA-BDD):
  - persona_autorizada.usuario_id INT NULL, FK a auth_user (ON DELETE SET NULL)   -> RF-ACC-02
  - punto_acceso.device_key_hash VARCHAR(255) NULL (clave del agente del lector)
  - evento_acceso.evento_externo_id VARCHAR(36) NULL + UNIQUE (punto_acceso_id, evento_externo_id)
Igual que en inventario/0001, se aplica solo en MySQL y solo lo que falta.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _columnas(schema_editor, tabla):
    conexion = schema_editor.connection
    if conexion.vendor != 'mysql' or tabla not in conexion.introspection.table_names():
        return None
    with conexion.cursor() as cursor:
        return {c.name for c in conexion.introspection.get_table_description(cursor, tabla)}


def _restricciones(schema_editor, tabla):
    with schema_editor.connection.cursor() as cursor:
        return set(schema_editor.connection.introspection.get_constraints(cursor, tabla))


def ampliar_esquema(apps, schema_editor):
    columnas = _columnas(schema_editor, 'persona_autorizada')
    if columnas is not None and 'usuario_id' not in columnas:
        schema_editor.execute(
            'ALTER TABLE persona_autorizada ADD COLUMN usuario_id INT NULL, '
            'ADD KEY idx_persona_usuario (usuario_id), '
            'ADD CONSTRAINT fk_persona_usuario FOREIGN KEY (usuario_id) '
            'REFERENCES auth_user (id) ON DELETE SET NULL ON UPDATE RESTRICT'
        )
    columnas = _columnas(schema_editor, 'punto_acceso')
    if columnas is not None and 'device_key_hash' not in columnas:
        schema_editor.execute(
            "ALTER TABLE punto_acceso ADD COLUMN device_key_hash VARCHAR(255) NULL "
            "COMMENT 'Hash de la clave del agente del lector'"
        )
    columnas = _columnas(schema_editor, 'evento_acceso')
    if columnas is not None:
        if 'evento_externo_id' not in columnas:
            schema_editor.execute('ALTER TABLE evento_acceso ADD COLUMN evento_externo_id VARCHAR(36) NULL')
        if 'uq_evt_acceso_externo' not in _restricciones(schema_editor, 'evento_acceso'):
            schema_editor.execute(
                'ALTER TABLE evento_acceso ADD UNIQUE KEY uq_evt_acceso_externo (punto_acceso_id, evento_externo_id)'
            )


class Migration(migrations.Migration):

    initial = True
    # MySQL no puede revertir DDL dentro de una transacción; Django exige ejecutarla sin atomic.
    atomic = False

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mediciones', '0002_ubicacion_umbralambiental'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonaAutorizada',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=150)),
                ('identificador_biometrico_externo', models.CharField(max_length=255, unique=True)),
                ('estado', models.CharField(default='Activo', max_length=8)),
                ('usuario', models.ForeignKey(blank=True, db_column='usuario_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='persona_autorizada', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'persona_autorizada', 'managed': False},
        ),
        migrations.CreateModel(
            name='PuntoAcceso',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=150)),
                ('estado', models.CharField(default='Activo', max_length=8)),
                ('device_key_hash', models.CharField(blank=True, max_length=255, null=True)),
                ('ubicacion', models.ForeignKey(db_column='ubicacion_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='puntos_acceso', to='mediciones.ubicacion')),
            ],
            options={'db_table': 'punto_acceso', 'managed': False},
        ),
        migrations.CreateModel(
            name='PermisoAcceso',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('vigencia_inicio', models.DateField()),
                ('vigencia_fin', models.DateField(blank=True, null=True)),
                ('estado', models.CharField(default='Activo', max_length=8)),
                ('persona', models.ForeignKey(db_column='persona_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='permisos', to='accesos.personaautorizada')),
                ('punto_acceso', models.ForeignKey(db_column='punto_acceso_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='permisos', to='accesos.puntoacceso')),
            ],
            options={'db_table': 'permiso_acceso', 'managed': False},
        ),
        migrations.CreateModel(
            name='PermisoDia',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('dia_semana', models.CharField(max_length=3)),
                ('hora_inicio', models.TimeField()),
                ('hora_fin', models.TimeField()),
                ('permiso', models.ForeignKey(db_column='permiso_acceso_id', on_delete=django.db.models.deletion.CASCADE, related_name='dias', to='accesos.permisoacceso')),
            ],
            options={'db_table': 'permiso_dia', 'managed': False},
        ),
        migrations.CreateModel(
            name='EventoAcceso',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('identificador_biometrico_externo', models.CharField(max_length=255)),
                ('fecha_hora', models.DateTimeField()),
                ('resultado', models.CharField(max_length=9)),
                ('motivo', models.CharField(blank=True, max_length=255, null=True)),
                ('evento_externo_id', models.CharField(blank=True, max_length=36, null=True)),
                ('persona', models.ForeignKey(blank=True, db_column='persona_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to='accesos.personaautorizada')),
                ('punto_acceso', models.ForeignKey(db_column='punto_acceso_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='eventos', to='accesos.puntoacceso')),
            ],
            options={'db_table': 'evento_acceso', 'managed': False, 'unique_together': {('punto_acceso', 'evento_externo_id')}},
        ),
        migrations.RunPython(ampliar_esquema, migrations.RunPython.noop),
    ]
