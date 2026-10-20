"""Catálogo de estados de activo (RF-CAT-03).

Cambios en tablas del script SQL (actualizar SICMA-BDD):
  - tabla nueva estado_activo, con los 5 valores del enum original
  - activo.estado pasa de ENUM(...) a VARCHAR(50) NOT NULL DEFAULT 'Operativo'
Igual que en la 0001, el ALTER se aplica solo en MySQL y si la columna sigue siendo ENUM.
"""
from django.db import migrations, models


# (nombre, etiqueta, color, es_sistema)
ESTADOS_INICIALES = (
    ('Operativo', 'Operativo', 'success', True),
    ('Degradado', 'Degradado', 'warning', False),
    ('En_mantenimiento', 'En mantenimiento', 'tertiary', False),
    ('Fuera_de_servicio', 'Fuera de servicio', 'danger', False),
    ('Retirado', 'Retirado', 'medium', True),
)
ENUM_ORIGINAL = "ENUM('Operativo','Degradado','En_mantenimiento','Fuera_de_servicio','Retirado')"


def _tipo_columna_estado(schema_editor):
    conexion = schema_editor.connection
    if conexion.vendor != 'mysql' or 'activo' not in conexion.introspection.table_names():
        return None
    with conexion.cursor() as cursor:
        cursor.execute(
            'SELECT DATA_TYPE FROM information_schema.COLUMNS '
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activo' AND COLUMN_NAME = 'estado'"
        )
        fila = cursor.fetchone()
    return fila[0].lower() if fila else None


def ampliar_columna_estado(apps, schema_editor):
    if _tipo_columna_estado(schema_editor) == 'enum':
        schema_editor.execute(
            "ALTER TABLE activo MODIFY estado VARCHAR(50) NOT NULL DEFAULT 'Operativo' "
            "COMMENT 'Nombre en estado_activo (RF-CAT-03)'"
        )


def restaurar_enum_estado(apps, schema_editor):
    # Falla si algún activo quedó con un estado creado después; es lo esperado.
    if _tipo_columna_estado(schema_editor) == 'varchar':
        schema_editor.execute(f"ALTER TABLE activo MODIFY estado {ENUM_ORIGINAL} NOT NULL DEFAULT 'Operativo'")


def crear_tabla_estados(apps, schema_editor):
    # Idempotente: la cuenta de la aplicación no tiene DROP, así que no se puede limpiar a mano.
    EstadoActivo = apps.get_model('inventario', 'EstadoActivo')
    if EstadoActivo._meta.db_table not in schema_editor.connection.introspection.table_names():
        schema_editor.create_model(EstadoActivo)


def eliminar_tabla_estados(apps, schema_editor):
    EstadoActivo = apps.get_model('inventario', 'EstadoActivo')
    if EstadoActivo._meta.db_table in schema_editor.connection.introspection.table_names():
        schema_editor.delete_model(EstadoActivo)


def cargar_estados(apps, schema_editor):
    EstadoActivo = apps.get_model('inventario', 'EstadoActivo')
    for orden, (nombre, etiqueta, color, es_sistema) in enumerate(ESTADOS_INICIALES, start=1):
        EstadoActivo.objects.get_or_create(
            nombre=nombre,
            defaults={'etiqueta': etiqueta, 'color': color, 'es_sistema': es_sistema, 'orden': orden * 10},
        )


class Migration(migrations.Migration):

    # MySQL no puede revertir DDL dentro de una transacción; Django exige ejecutarla sin atomic.
    atomic = False

    dependencies = [
        ('inventario', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='EstadoActivo',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nombre', models.CharField(max_length=50, unique=True)),
                        ('etiqueta', models.CharField(max_length=100)),
                        ('color', models.CharField(default='medium', max_length=20)),
                        ('activo', models.BooleanField(default=True)),
                        ('es_sistema', models.BooleanField(default=False)),
                        ('orden', models.PositiveSmallIntegerField(default=0)),
                    ],
                    options={'db_table': 'estado_activo', 'ordering': ['orden', 'nombre']},
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(crear_tabla_estados, eliminar_tabla_estados),
        migrations.RunPython(cargar_estados, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='activo',
            name='estado',
            field=models.CharField(default='Operativo', max_length=50),
        ),
        migrations.RunPython(ampliar_columna_estado, restaurar_enum_estado),
    ]
