"""Supervise one local worker and beat for email-only or operations mode."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def lock_file(path):
    handle = path.open('a+b')
    handle.seek(0)
    if os.name == 'nt':
        import msvcrt
        if not path.stat().st_size:
            handle.write(b'0');handle.flush();handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


class Command(BaseCommand):
    help = 'Supervise Celery worker and beat until stopped.'

    def handle(self, *args, **options):
        if os.environ.get('RAILWISE_BACKGROUND_MODE') not in ('notifications', 'operations'):
            raise CommandError('Set RAILWISE_BACKGROUND_MODE to notifications or operations first.')
        if os.environ.get('RAILWISE_BACKGROUND_MODE') == 'notifications' and set(settings.CELERY_BEAT_SCHEDULE) != {'send-booking-notifications'}:
            raise CommandError('Email-only schedule required.')
        runtime = settings.BASE_DIR.parent / '.runtime' / 'notification-services'
        runtime.mkdir(parents=True, exist_ok=True)
        try:
            lock = lock_file(runtime/'supervisor.lock')
        except OSError:
            raise CommandError('Notification services are already running.') from None
        from redis import Redis
        Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=5, socket_timeout=5).ping()
        from django.db import connection
        connection.ensure_connection()
        connection.close()
        status_path = runtime/'status.json'
        stop_path = runtime/'stop.request'
        stop_path.unlink(missing_ok=True)
        stopping = False
        def stop(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        commands = {
            'worker': [sys.executable, '-m', 'celery', '-A', 'railway_core', 'worker',
                '--pool=solo', '--concurrency=1', '-Q', 'railwise_notifications,celery' if os.environ.get('RAILWISE_BACKGROUND_MODE') == 'operations' else 'railwise_notifications',
                '--hostname=railwise-email@%h', '--loglevel=INFO', '--without-gossip', '--without-mingle'],
            'beat': [sys.executable, '-m', 'celery', '-A', 'railway_core', 'beat', '--loglevel=INFO',
                '--schedule='+str(runtime/'beat-schedule'), '--pidfile='+str(runtime/'beat.pid')],
        }
        # The singleton supervisor lock prevents duplicate schedulers. Windows
        # can leave a PID file behind after a PC shutdown; let Celery manage
        # no PID file here, since this supervisor owns the child lifecycle.
        commands['beat'] = [arg for arg in commands['beat'] if not arg.startswith('--pidfile=')]
        commands['beat'].append('--pidfile=')
        children = {}; logs = {}; next_restart = {}; starts = {}
        try:
            while not stopping and not stop_path.exists():
                for name, command in commands.items():
                    child = children.get(name)
                    if child and child.poll() is None:
                        continue
                    if child and name not in next_restart:
                        next_restart[name] = time.time()+5
                    if time.time() < next_restart.get(name, 0):
                        continue
                    if name not in logs:
                        logs[name] = (runtime/f'{name}.log').open('ab', buffering=0)
                    if name == 'beat' and child and child.poll() is not None:
                        pidfile=runtime/'beat.pid'
                        if pidfile.exists() and pidfile.read_text().strip() == str(child.pid):
                            pidfile.unlink()
                    children[name] = subprocess.Popen(command, cwd=settings.BASE_DIR, env=os.environ.copy(),
                        stdout=logs[name], stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    starts[name] = starts.get(name, 0)+1
                    next_restart.pop(name, None)
                status = {'supervisor_pid':os.getpid(), 'updated_at':time.time(), 'mode':os.environ.get('RAILWISE_BACKGROUND_MODE'),
                    'children': {name:{'pid':child.pid,'running':child.poll() is None,'starts':starts[name]}
                        for name,child in children.items()}}
                temp = runtime/'status.tmp'
                temp.write_text(json.dumps(status),encoding='utf-8')
                try:
                    temp.replace(status_path)
                except PermissionError:
                    # Windows status readers can briefly hold a non-delete-sharing handle.
                    pass
                time.sleep(1)
        finally:
            for child in children.values():
                if child.poll() is None:
                    child.terminate()
            for child in children.values():
                try: child.wait(timeout=15)
                except subprocess.TimeoutExpired: child.kill();child.wait()
            for log in logs.values():log.close()
            status_path.unlink(missing_ok=True)
            stop_path.unlink(missing_ok=True)
            # Beat was our child and is now stopped; clear its stale PID on Windows.
            (runtime/'beat.pid').unlink(missing_ok=True)
            lock.close()
