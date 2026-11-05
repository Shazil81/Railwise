import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from django.conf import settings
from django.test import SimpleTestCase
from .management.commands.run_notification_services import lock_file


class BackgroundConfigTests(SimpleTestCase):
    def test_operations_profile_schedules_refund_recovery(self):
        env=os.environ.copy();env['RAILWISE_BACKGROUND_MODE']='operations'
        result=subprocess.run([sys.executable,'-c',
            "from django.conf import settings; import json; print(json.dumps(settings.CELERY_BEAT_SCHEDULE))"],
            cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,check=True,timeout=30)
        schedule=json.loads(result.stdout)
        self.assertEqual(schedule['recover-payments-and-refunds']['schedule'],60.0)
        self.assertIn('send-booking-notifications',schedule)

    def test_email_only_profile_schedules_no_gateway_jobs(self):
        env=os.environ.copy();env['RAILWISE_BACKGROUND_MODE']='notifications'
        result=subprocess.run([sys.executable,'-c',
            "from django.conf import settings; import json; print(json.dumps(settings.CELERY_BEAT_SCHEDULE))"],
            cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,check=True,timeout=30)
        schedule=json.loads(result.stdout)
        self.assertEqual(set(schedule),{'send-booking-notifications'})
        self.assertEqual(schedule['send-booking-notifications']['options']['queue'],'railwise_notifications')
        self.assertEqual(schedule['send-booking-notifications']['options']['expires'],60)

    def test_normal_profile_retains_existing_recovery_schedules(self):
        env=os.environ.copy();env.pop('RAILWISE_BACKGROUND_MODE',None)
        result=subprocess.run([sys.executable,'-c',
            "from django.conf import settings; import json; print(json.dumps(list(settings.CELERY_BEAT_SCHEDULE)))"],
            cwd=settings.BASE_DIR,env=env,capture_output=True,text=True,check=True,timeout=30)
        self.assertIn('recover-payments-and-refunds',json.loads(result.stdout))
        self.assertIn('sweep-expired-holds',json.loads(result.stdout))

    def test_singleton_lock_rejects_duplicate_supervisor(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'supervisor.lock'
            handle=lock_file(path)
            try:
                with self.assertRaises(OSError):lock_file(path)
            finally:handle.close()
            next_handle=lock_file(path)
            next_handle.close()
