import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import config from '../vite.config.ts';

test('development proxy follows the normal Django runserver port and explains connection failures', () => {
  const previous = process.env.API_PROXY_TARGET;
  process.env.API_PROXY_TARGET = '';
  try {
    const settings = config({ mode: 'test', command: 'serve' });
    const proxy = settings.server.proxy['/api'];
    assert.equal(proxy.target, 'http://127.0.0.1:8000');
    const events = new EventEmitter();
    proxy.configure(events);
    let status, body;
    events.emit('error', new Error('ECONNREFUSED'), {}, {
      headersSent: false,
      writeHead(value) { status = value; },
      end(value) { body = JSON.parse(value); },
    });
    assert.equal(status, 503);
    assert.match(body.detail, /python manage.py runserver/);
    process.env.API_PROXY_TARGET = 'http://127.0.0.1:8010';
    assert.equal(config({ mode: 'test', command: 'serve' }).server.proxy['/api'].target, process.env.API_PROXY_TARGET);
  } finally {
    if (previous === undefined) delete process.env.API_PROXY_TARGET;
    else process.env.API_PROXY_TARGET = previous;
  }
});
