"""Inventario: catálogo de tipos y ampliación aditiva del esquema del equipo.

Cambios en tablas del script SQL (actualizar SICMA-BDD):
  - activo.responsable_id INT NULL, FK a auth_user (ON DELETE SET NULL)  -> RF-ACT-04, RF-CAT-05
  - ubicacion.activa TINYINT(1) NOT NULL DEFAULT 1                       -> RF-CAT-01, RN-02
Se aplican solo en MySQL y si la tabla existe (en las pruebas las crea el propio test).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


TIPOS_INICIALES = (
    'Almacenamiento', 'Firewall', 'Otro', 'Rack', 'Router', 'Sensor', 'Servidor', 'Switch', 'UPS',
)


def _columnas(schema_editor, tabla):
    conexion = schema_editor.connection
    if conexion.vendor != 'mysql' or tabla not in conexion.introspection.table_names():
        return None
    with conexion.cursor() as cursor:
        return {c.name for c in conexion.introspection.get_table_description(cursor, tabla)}


def ampliar_esquema(apps, schema_editor):
    columnas = _columnas(schema_editor, 'activo')
    if columnas is not None and 'responsable_id' not in columnas:
        schema_editor.execute(
            'ALTER TABLE activo ADD COLUMN responsable_id INT NULL, '
            'ADD KEY idx_activo_responsable (responsable_id), '
            'ADD CONSTRAINT fk_activo_responsable FOREIGN KEY (responsable_id) '
            'REFERENCES auth_user (id) ON DELETE SET NULL ON UPDATE RESTRICT'
        )
    columnas = _columnas(schema_editor, 'ubicacion')
    if columnas is not None and 'activa' not in columnas:
        schema_editor.execute(
            "ALTER TABLE ubicacion ADD COLUMN activa TINYINT(1) NOT NULL DEFAULT 1 "
            "COMMENT 'Baja logica (RN-02)'"
        )


def revertir_esquema(apps, schema_editor):
    columnas = _columnas(schema_editor, 'activo')
    if columnas is not None and 'responsable_id' in columnas:
        schema_editor.execute('ALTER TABLE activo DROP FOREIGN KEY fk_activo_responsable')
        schema_editor.execute('ALTER TABLE activo DROP KEY idx_activo_responsable, DROP COLUMN responsable_id')
    columnas = _columnas(schema_editor, 'ubicacion')
    if columnas is not None and 'activa' in columnas:
        schema_editor.execute('ALTER TABLE ubicacion DROP COLUMN activa')


def crear_tabla_tipos(apps, schema_editor):
    # Idempotente: la cuenta de la aplicación no tiene DROP, así que no se puede limpiar a mano.
    TipoActivo = apps.get_model('inventario', 'TipoActivo')
    if TipoActivo._meta.db_table not in schema_editor.connection.introspection.table_names():
        schema_editor.create_model(TipoActivo)


def eliminar_tabla_tipos(apps, schema_editor):
    TipoActivo = apps.get_model('inventario', 'TipoActivo')
    if TipoActivo._meta.db_table in schema_editor.connection.introspection.table_names():
        schema_editor.delete_model(TipoActivo)


def cargar_tipos(apps, schema_editor):
    TipoActivo = apps.get_model('inventario', 'TipoActivo')
    for nombre in TIPOS_INICIALES:
        TipoActivo.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    initial = True
    # MySQL no puede revertir DDL dentro de una transacción; Django exige ejecutarla sin atomic.
    atomic = False

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mediciones', '0002_ubicacion_umbralambiental'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='TipoActivo',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nombre', models.CharField(max_length=100, unique=True)),
                        ('activo', models.BooleanField(default=True)),
                    ],
                    options={'db_table': 'tipo_activo', 'ordering': ['nombre']},
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(crear_tabla_tipos, eliminar_tabla_tipos),
        migrations.CreateModel(
            name='Activo',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('codigo', models.CharField(max_length=50, unique=True)),
                ('nombre', models.CharField(max_length=200)),
                ('tipo', models.CharField(blank=True, max_length=100, null=True)),
                ('marca', models.CharField(blank=True, max_length=100, null=True)),
                ('modelo', models.CharField(blank=True, max_length=100, null=True)),
                ('numero_serie', models.CharField(max_length=150, unique=True)),
                ('estado', models.CharField(default='Operativo', max_length=17)),
                ('criticidad', models.CharField(default='Media', max_length=7)),
                ('fecha_alta', models.DateTimeField()),
                ('observaciones', models.TextField(blank=True, null=True)),
                ('responsable', models.ForeignKey(blank=True, db_column='responsable_id', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='activos_a_cargo', to=settings.AUTH_USER_MODEL)),
                ('ubicacion', models.ForeignKey(db_column='ubicacion_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='activos', to='mediciones.ubicacion')),
            ],
            options={'db_table': 'activo', 'managed': False},
        ),
        migrations.CreateModel(
            name='HistorialActivo',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('campo_modificado', models.CharField(max_length=100)),
                ('valor_anterior', models.TextField(blank=True, null=True)),
                ('valor_nuevo', models.TextField(blank=True, null=True)),
                ('fecha_hora', models.DateTimeField()),
                ('activo', models.ForeignKey(db_column='activo_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='historial', to='inventario.activo')),
                ('usuario', models.ForeignKey(db_column='usuario_id', on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'historial_activo', 'managed': False},
        ),
        migrations.RunPython(ampliar_esquema, revertir_esquema),
        migrations.RunPython(cargar_tipos, migrations.RunPython.noop),
    ]
