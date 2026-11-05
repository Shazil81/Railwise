import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';

test('cloud API base works for both requests and direct SSE, with a local proxy default', async()=>{
  for (const [configured,expected] of [['','/api'],['https://railwise-api.onrender.com/api/','https://railwise-api.onrender.com/api']]) {
    const server=await createServer({define:{'import.meta.env.VITE_API_BASE_URL':JSON.stringify(configured)},server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'});
    try {
      const {API_BASE_URL}=await server.ssrLoadModule('/src/apiBase.ts');
      assert.equal(API_BASE_URL,expected);
    } finally {await server.close();}
  }
});
