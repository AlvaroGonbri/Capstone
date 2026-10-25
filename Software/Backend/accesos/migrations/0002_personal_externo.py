"""Personal externo: ficha, habilitación manual y enrolamiento desde SICMA.

Cambios en tablas del script SQL (actualizar SICMA-BDD):
  - persona_autorizada: rut VARCHAR(12) UNIQUE NULL, empresa VARCHAR(150) NULL,
    huella_registrada_en DATETIME NULL, huella_registrada_por_id INT NULL (FK auth_user)
Tablas nuevas de SICMA: cambio_habilitacion y solicitud_enrolamiento.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


COLUMNAS = (
    ('rut', 'VARCHAR(12) NULL'),
    ('empresa', 'VARCHAR(150) NULL'),
    ('huella_registrada_en', "DATETIME NULL COMMENT 'UTC'"),
    ('huella_registrada_por_id', 'INT NULL'),
)


def ampliar_persona(apps, schema_editor):
    conexion = schema_editor.connection
    if conexion.vendor != 'mysql' or 'persona_autorizada' not in conexion.introspection.table_names():
        return
    with conexion.cursor() as cursor:
        columnas = {c.name for c in conexion.introspection.get_table_description(cursor, 'persona_autorizada')}
        restricciones = set(conexion.introspection.get_constraints(cursor, 'persona_autorizada'))
    faltan = [f'ADD COLUMN {nombre} {tipo}' for nombre, tipo in COLUMNAS if nombre not in columnas]
    if faltan:
        schema_editor.execute('ALTER TABLE persona_autorizada ' + ', '.join(faltan))
    if 'uq_persona_rut' not in restricciones:
        schema_editor.execute('ALTER TABLE persona_autorizada ADD UNIQUE KEY uq_persona_rut (rut)')
    if 'fk_persona_huella_por' not in restricciones:
        schema_editor.execute(
            'ALTER TABLE persona_autorizada ADD CONSTRAINT fk_persona_huella_por FOREIGN KEY (huella_registrada_por_id) '
            'REFERENCES auth_user (id) ON DELETE SET NULL ON UPDATE RESTRICT'
        )


class Migration(migrations.Migration):

    # MySQL no puede revertir DDL dentro de una transacción; Django exige ejecutarla sin atomic.
    atomic = False

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accesos', '0001_initial'),
    ]

    operations = [
        # persona_autorizada es managed=False: estos AddField solo actualizan el estado; el ALTER va abajo.
        migrations.AddField(
            model_name='personaautorizada', name='rut',
            field=models.CharField(blank=True, max_length=12, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='personaautorizada', name='empresa',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='personaautorizada', name='huella_registrada_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='personaautorizada', name='huella_registrada_por',
            field=models.ForeignKey(blank=True, db_column='huella_registrada_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(ampliar_persona, migrations.RunPython.noop),
        migrations.CreateModel(
            name='CambioHabilitacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('habilitada', models.BooleanField()),
                ('motivo', models.CharField(blank=True, default='', max_length=255)),
                ('fecha_hora', models.DateTimeField()),
                ('persona', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='cambios_habilitacion', to='accesos.personaautorizada')),
                ('usuario', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'cambio_habilitacion', 'ordering': ['-fecha_hora', '-id']},
        ),
        migrations.CreateModel(
            name='SolicitudEnrolamiento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(default='Pendiente', max_length=10)),
                ('mensaje', models.CharField(blank=True, default='', max_length=255)),
                ('fecha_solicitud', models.DateTimeField()),
                ('fecha_inicio', models.DateTimeField(blank=True, null=True)),
                ('fecha_fin', models.DateTimeField(blank=True, null=True)),
                ('persona', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='enrolamientos', to='accesos.personaautorizada')),
                ('punto_acceso', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='enrolamientos', to='accesos.puntoacceso')),
                ('solicitada_por', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'solicitud_enrolamiento', 'ordering': ['-id']},
        ),
    ]
