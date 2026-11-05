from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('bookings', '0010_train_service_validity')]
    operations = [
        migrations.AddField(model_name='booking', name='confirmed_berths_only', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='booking', name='consider_auto_upgrade', field=models.BooleanField(default=False)),
    ]
