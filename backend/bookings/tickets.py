"""Owner-only confirmation snapshot and server-rendered portfolio demo ticket."""
from .berths import LABELS
from .booking_display import journey_details
from .rules import IST
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from .models import Booking, Journey, PaymentAttempt, Refund
from .services import group_members

class TicketUnavailable(APIException):
    status_code = 409
    default_detail = 'A ticket is available only for a complete, payment-verified confirmed booking.'


def ticket_available(booking):
    if booking.group_parent_id or booking.status != 'CONFIRMED' or not booking.razorpay_payment_id or not booking.razorpay_order_id:
        return False
    if booking.journey.train.stops.filter(sequence__in=[booking.from_seq, booking.to_seq]).count() != 2:
        return False
    members = list(group_members(booking).select_related('seat'))
    if any(m.status != 'CONFIRMED' or not m.seat or not m.passenger_name or not m.passenger_age or not m.passenger_gender for m in members):
        return False
    if not booking.contact_email or not booking.contact_phone:
        return False
    amount = int(sum(m.amount for m in members) * 100)
    attempt = PaymentAttempt.objects.filter(booking=booking, payment_id=booking.razorpay_payment_id,
        order_id=booking.razorpay_order_id, state='CAPTURED', amount_paise=amount, currency='INR').first()
    return bool(attempt and not Refund.objects.filter(attempt=attempt).exclude(state='FAILED').exists())


@transaction.atomic
def confirmation_snapshot(booking_id, user):
    from django.shortcuts import get_object_or_404
    booking = get_object_or_404(Booking, pk=booking_id, user=user, group_parent__isnull=True)
    Journey.objects.select_for_update().get(pk=booking.journey_id)
    booking = Booking.objects.select_for_update().select_related('journey__train').get(pk=booking.id)
    if not ticket_available(booking):
        raise TicketUnavailable()
    members = list(group_members(booking).select_related('seat'))
    stops = {s.sequence: s.station for s in booking.journey.train.stops.select_related('station')}
    attempt = booking.payment_attempts.get(payment_id=booking.razorpay_payment_id)
    total = sum(m.amount for m in members)
    return {
        **journey_details(booking),
        'preferences':{'confirmed_berths_only':booking.confirmed_berths_only,'consider_auto_upgrade':booking.consider_auto_upgrade},
        'reference': f'RW-{booking.id:08d}', 'booking_id': booking.id, 'status': 'CONFIRMED',
        'issued_at': timezone.now().isoformat(), 'booked_at': booking.created_at.isoformat(),
        'train': booking.journey.train.name, 'train_number': booking.journey.train.number,
        'journey_date': booking.boarding_date.isoformat(),
        'origin': {'name': stops[booking.from_seq].name, 'code': stops[booking.from_seq].code},
        'destination': {'name': stops[booking.to_seq].name, 'code': stops[booking.to_seq].code},
        'passengers': [{'name': m.passenger_name, 'age': m.passenger_age, 'gender': m.passenger_gender,
            'coach': m.seat.coach, 'seat_number': m.seat.number, 'berth_type':m.seat.allocated_berth,
            'country':m.passenger_country,'berth_preference':m.berth_preference,'fare': format(m.amount, '.2f')} for m in members],
        'contact': {'email': booking.contact_email, 'phone': booking.contact_phone},
        'fare': {'base_fare': format(total, '.2f'), 'booking_fee': '0.00', 'total': format(total, '.2f'), 'currency': 'INR'},
        'payment': {'provider': 'Razorpay', 'status': 'CAPTURED', 'payment_id': attempt.payment_id,
            'method':attempt.method or None,'captured_at':attempt.captured_at.isoformat() if attempt.captured_at else None,
            'order_id': attempt.order_id, 'amount': format(Decimal(attempt.amount_paise)/100, '.2f'),
            'currency': attempt.currency, 'recorded_at': attempt.created_at.isoformat()},
        'notice': 'PORTFOLIO DEMO - NOT VALID FOR TRAVEL. Not an IRCTC ticket or railway PNR. Routes and fares are sample data.',
    }


@lru_cache(maxsize=1)
def ticket_font():
    import reportlab
    candidates = [getattr(settings, 'TICKET_FONT_PATH', ''),
        'C:/Windows/Fonts/arial.ttf',
        str(Path(reportlab.__file__).parent/'fonts'/'Vera.ttf')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            pdfmetrics.registerFont(TTFont('RailwiseTicket', candidate))
            return 'RailwiseTicket'
    raise TicketUnavailable('A PDF font is not available on the server.')


def render_ticket(snapshot):
    """Render a readable, paginated ticket from the verified server snapshot."""
    font = ticket_font()
    supported = pdfmetrics.getFont(font).face.charToGlyph
    if any(ord(c) > 127 and ord(c) not in supported for c in str(snapshot)):
        raise TicketUnavailable('The server PDF font cannot render these passenger characters. Configure TICKET_FONT_PATH with a suitable font.')
    import reportlab
    bold_path = Path('C:/Windows/Fonts/arialbd.ttf') if font and Path('C:/Windows/Fonts/arialbd.ttf').exists() else Path(reportlab.__file__).parent/'fonts'/'VeraBd.ttf'
    bold = font
    if bold_path.is_file() and not getattr(settings, 'TICKET_FONT_PATH', ''):
        pdfmetrics.registerFont(TTFont('RailwiseTicketBold', str(bold_path)))
        bold = 'RailwiseTicketBold'
    ink = colors.HexColor('#243754')
    muted = colors.HexColor('#526581')
    blue = colors.HexColor('#244c9a')
    green = colors.HexColor('#176951')
    width = A4[0] - 80
    body = ParagraphStyle('ticket-body', fontName=font, fontSize=10.5, leading=15, textColor=ink, wordWrap='CJK', splitLongWords=True)
    small = ParagraphStyle('ticket-small', parent=body, fontSize=8.5, leading=12, textColor=muted)
    label = ParagraphStyle('ticket-label', parent=small, fontName=bold)
    strong = ParagraphStyle('ticket-strong', parent=body, fontName=bold, fontSize=12, leading=17)
    large = ParagraphStyle('ticket-large', parent=strong, fontSize=22, leading=28, textColor=blue)
    white = ParagraphStyle('ticket-white', parent=strong, textColor=colors.white)
    heading = ParagraphStyle('ticket-heading', parent=strong, fontSize=13, leading=18, spaceBefore=10, spaceAfter=7, keepWithNext=True)
    def para(value, style=body):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), style)
    def table(rows, widths, background=None, padding=11):
        result = Table(rows, colWidths=widths, hAlign='LEFT')
        commands = [('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),padding),('RIGHTPADDING',(0,0),(-1,-1),padding),('TOPPADDING',(0,0),(-1,-1),padding),('BOTTOMPADDING',(0,0),(-1,-1),padding)]
        if background:
            commands.append(('BACKGROUND',(0,0),(-1,-1),colors.HexColor(background)))
        result.setStyle(TableStyle(commands))
        return result
    def local_datetime(value):
        if not value:
            return None
        result = datetime.fromisoformat(value)
        if timezone.is_naive(result):
            result = result.replace(tzinfo=IST)
        return result.astimezone(IST)

    departure, arrival = local_datetime(snapshot.get('departure_at')), local_datetime(snapshot.get('arrival_at'))
    booked = local_datetime(snapshot.get('booked_at'))
    duration = snapshot.get('duration_minutes')
    duration_text = f'{duration // 60}h {duration % 60}m' if duration is not None else 'Not recorded'
    schedule = ParagraphStyle('ticket-schedule', parent=strong, fontSize=16, leading=21, textColor=blue)

    def station_details(label_text, station, instant, fallback_date=None):
        return [para(label_text, label), para(station['code'], large), para(station['name']),
                para(instant.strftime('%H:%M IST') if instant else 'Time not recorded', schedule),
                para(instant.strftime('%d %b %Y') if instant else fallback_date or 'Date not recorded', small)]

    date = datetime.fromisoformat(snapshot['journey_date']).strftime('%d %B %Y')
    header = table([[[para('Railwise', ParagraphStyle('brand',parent=white,fontSize=25,leading=31)),
        para('Booked on: '+(booked.strftime('%d %b %Y %H:%M IST') if booked else 'Not recorded'),
             ParagraphStyle('booked',parent=small,textColor=colors.HexColor('#e2e9ff')))],
        [para('BOOKING REFERENCE',ParagraphStyle('white-label',parent=small,textColor=colors.HexColor('#dce5ff'))),para(snapshot['reference'],white)]]], [width*.57,width*.43], '#24458d',10)
    success = table([[para('CONFIRMED - PAYMENT VERIFIED',ParagraphStyle('success',parent=strong,textColor=green)),para(f"{len(snapshot['passengers'])} passenger(s)",strong)]],[width*.72,width*.28],'#e7f5ee',10)
    notice = para('PORTFOLIO DEMO - NOT VALID FOR TRAVEL. Not an IRCTC ticket or railway PNR.',ParagraphStyle('demo',parent=small,textColor=colors.HexColor('#80591e'),spaceBefore=9,spaceAfter=12))
    route = table([[station_details('DEPARTURE / FROM', snapshot['origin'], departure,
                                   datetime.fromisoformat(snapshot['journey_date']).strftime('%d %b %Y')),
                    station_details('ARRIVAL / TO', snapshot['destination'], arrival)],
        [[para(snapshot['train'],strong),para('Train #'+str(snapshot['train_number']),small),
          para(snapshot.get('class_name') or 'Class not recorded', strong)],
         [para('JOURNEY DATE',label),para(date,strong),para('Duration: '+duration_text,body)]]],
        [width/2,width/2],'#eef3ff',8)
    story = [header,success,notice,route,para('Passengers & confirmed allocation',heading)]
    for i,p in enumerate(snapshot['passengers'],1):
        identity = [para(f"{i:02d}  {p['name']}",strong),
            para(f"{p['age']} years | {p['gender']}"+(f" | {p['country']}" if p.get('country') else ''),small),
            para('Fare: INR '+p['fare'],small)]
        allocation = table([[identity,
            [para('COACH',label),para(p['coach'],large)],
            [para('SEAT',label),para(p['seat_number'],large)],
            [para('BERTH TYPE',label),para(LABELS.get(p.get('berth_type','NA'),'Seat'),strong)]]],
            [width*.43,width*.16,width*.14,width*.27], '#eeebfb',10)
        allocation.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),colors.HexColor('#f5f6fc'))]))
        story.append(KeepTogether([allocation,Spacer(1,6)]))
    recorded = datetime.fromisoformat(snapshot['payment']['recorded_at']).astimezone(timezone.get_current_timezone()).strftime('%d %b %Y %H:%M IST')
    payment = [para('Payment details',heading),table([
        [[para('PROVIDER / STATUS',label),para(snapshot['payment']['provider']+' / CAPTURED - verified',strong)],
         [para('PAYMENT ID',label),para(snapshot['payment']['payment_id'])]],
        [[para('ORDER ID',label),para(snapshot['payment']['order_id'])],
         [para('PAYMENT RECORDED',label),para(recorded)]]],
        [width*.55,width*.45],'#f3f6fc',7)]
    total = table([[[para('Passenger fares',label),para('INR '+snapshot['fare']['base_fare'],strong)],
                    [para('Booking fee',label),para('INR '+snapshot['fare']['booking_fee'],strong)],
                    [para('TOTAL PAID',label),para('INR '+snapshot['fare']['total'],ParagraphStyle('paid',parent=large,textColor=green,fontSize=19,leading=26))]]], [width*.32,width*.25,width*.43], '#e7f5ee',11)
    story += [KeepTogether(payment+[Spacer(1,8),total]),KeepTogether([Spacer(1,10),para('Booking contact',strong),
        para(snapshot['contact']['email']+' | '+snapshot['contact']['phone']),Spacer(1,6),
        para('Sample project pricing. This downloaded ticket is a dated snapshot. Check booking history for the current cancellation or refund status.',small)])]
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,pagesize=A4,leftMargin=40,rightMargin=40,topMargin=32,bottomMargin=55,
        title=f"Railwise demo ticket {snapshot['reference']}",author='Railwise')
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#dce5f1'));canvas.line(40,40,A4[0]-40,40)
        canvas.setFont(font,8);canvas.setFillColor(muted)
        canvas.drawString(40,26,'DEMO - NOT VALID FOR TRAVEL')
        canvas.drawRightString(A4[0]-40,26,f"{snapshot['reference']} | Page {doc.page}")
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()
