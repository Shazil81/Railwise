from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('bookings', '0002_booking_amount_booking_razorpay_order_id_and_more')]
    operations = [
        migrations.AlterField(model_name='booking', name='razorpay_order_id',
            field=models.CharField(max_length=100, null=True, blank=True, unique=True)),
        migrations.AlterField(model_name='booking', name='razorpay_payment_id',
            field=models.CharField(max_length=100, null=True, blank=True, unique=True)),
    ]
