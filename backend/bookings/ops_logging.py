import json
import logging


class OperationsFormatter(logging.Formatter):
    def format(self, record):
        # Explicit allowlist: never serialize request data, exception text or credentials.
        return json.dumps({'event':'email_retry','actor_id':getattr(record,'actor_id',None),
            'notification_id':getattr(record,'notification_id',None),'outcome':getattr(record,'outcome',None)})
