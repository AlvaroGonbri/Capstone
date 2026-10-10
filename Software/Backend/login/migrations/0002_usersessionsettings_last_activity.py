from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('login', '0001_usersessionsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersessionsettings',
            name='last_activity_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
