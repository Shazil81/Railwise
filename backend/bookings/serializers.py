from rest_framework import serializers
from .models import Journey, Seat
from .services import validate_segment

class SegmentSerializer(serializers.Serializer):
    confirmed_berths_only = serializers.BooleanField(required=False, default=False)
    consider_auto_upgrade = serializers.BooleanField(required=False, default=False)
    journey_id = serializers.PrimaryKeyRelatedField(queryset=Journey.objects.all())
    from_seq = serializers.IntegerField(min_value=1)
    to_seq = serializers.IntegerField(min_value=1)
    travel_class = serializers.ChoiceField(choices=['SL','3A','2A','1A','CC','EC'],required=False,default='SL')
    quota = serializers.ChoiceField(choices=['GN','TQ'],required=False,default='GN')

    def validate(self, data):
        validate_segment(data['journey_id'], data['from_seq'], data['to_seq'])
        return data

class BookingSerializer(SegmentSerializer):
    seat_id = serializers.PrimaryKeyRelatedField(queryset=Seat.objects.all(), required=False)
    seat_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=6, required=False)

    def validate(self, data):
        super().validate(data)
        if ('seat_id' in data) == ('seat_ids' in data):
            raise serializers.ValidationError('Supply seat_ids or seat_id, not both.')
        ids = data.get('seat_ids', [data['seat_id'].id] if 'seat_id' in data else [])
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError('Each passenger needs a different seat.')
        if Seat.objects.filter(pk__in=ids, train_id=data['journey_id'].train_id).count() != len(ids):
            raise serializers.ValidationError('Choose seats belonging to this train.')
        data['seat_ids'] = ids
        return data

class PassengerSerializer(serializers.Serializer):
    country = serializers.CharField(max_length=80,required=False)
    berth_preference = serializers.ChoiceField(choices=['ANY','LB','MB','UB','SL','SU'],required=False)
    booking_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=100, min_length=2)
    age = serializers.IntegerField(min_value=1, max_value=120)
    gender = serializers.ChoiceField(choices=['Female', 'Male', 'Other', 'Prefer not to say'])

    def validate_name(self, value):
        value = ' '.join(value.split())
        if len(value) < 2 or not any(c.isalpha() for c in value) or any(not (c.isalpha() or c in " .'-") for c in value):
            raise serializers.ValidationError('Enter a valid passenger name.')
        return value

    def validate_country(self,value):
        if not all(c.isalpha() or c in " .'-" for c in value):
            raise serializers.ValidationError('Enter a country name.')
        return ' '.join(value.split())


class OtherPreferencesSerializer(serializers.Serializer):
    preferred_coach = serializers.RegexField(r'^[A-Z][A-Z0-9]{0,4}$',required=False,allow_blank=True)
    gstin = serializers.RegexField(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$',required=False,allow_blank=True)

class PassengerDetailsSerializer(OtherPreferencesSerializer):
    confirmed_berths_only = serializers.BooleanField(required=False)
    consider_auto_upgrade = serializers.BooleanField(required=False)
    passengers = PassengerSerializer(many=True, min_length=1, max_length=6)
    contact_email = serializers.EmailField()
    contact_phone = serializers.RegexField(r'^[6-9][0-9]{9}$')


class PaymentVerificationSerializer(serializers.Serializer):
    razorpay_order_id = serializers.RegexField(r'^order_[A-Za-z0-9_]+$', max_length=100)
    razorpay_payment_id = serializers.RegexField(r'^pay_[A-Za-z0-9_]+$', max_length=100)
    razorpay_signature = serializers.RegexField(r'^[a-f0-9]{64}$', max_length=64)


class NewPassengerSerializer(PassengerSerializer):
    booking_id = None


class AutomaticBookingSerializer(SegmentSerializer,OtherPreferencesSerializer):
    passengers = NewPassengerSerializer(many=True, min_length=1, max_length=6)
    contact_email = serializers.EmailField()
    contact_phone = serializers.RegexField(r'^[6-9][0-9]{9}$')
