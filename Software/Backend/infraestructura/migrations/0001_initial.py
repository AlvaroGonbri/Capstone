from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EstadoInfraestructura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ultimo_intento', models.DateTimeField(blank=True, null=True)),
                ('ultima_exitosa', models.DateTimeField(blank=True, null=True)),
                ('error', models.TextField(blank=True, default='')),
                ('activos', models.JSONField(blank=True, null=True)),
                ('estado', models.JSONField(blank=True, null=True)),
                ('hosts', models.JSONField(blank=True, null=True)),
                ('ultimo_webhook', models.DateTimeField(blank=True, null=True)),
            ],
            options={'db_table': 'estado_infraestructura', 'verbose_name': 'estado de infraestructura'},
        ),
    ]
