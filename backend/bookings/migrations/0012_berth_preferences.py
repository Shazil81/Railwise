from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('bookings','0011_booking_preferences')]
    operations=[
        migrations.AddField(model_name='seat',name='berth_type',field=models.CharField(max_length=3,blank=True,default='',choices=[('','Automatic demo layout'),('LB','Lower'),('MB','Middle'),('UB','Upper'),('SL','Side Lower'),('SU','Side Upper'),('NA','Seat')])),
        migrations.AddField(model_name='booking',name='berth_preference',field=models.CharField(max_length=3,default='ANY',choices=[('ANY','No preference'),('LB','Lower'),('MB','Middle'),('UB','Upper'),('SL','Side Lower'),('SU','Side Upper')]))
    ]
