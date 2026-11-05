from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('bookings', '0009_local_catalogue_pricing')]
    operations = [
        migrations.AddField(model_name='train', name='valid_from', field=models.DateField(null=True, blank=True)),
        migrations.AddField(model_name='train', name='valid_until', field=models.DateField(null=True, blank=True)),
    ]
