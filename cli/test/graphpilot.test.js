import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import net from 'node:net';
import test from 'node:test';

import { ensureRuntimePorts, getEnvFile, readEnvMap } from '../bin/graphpilot.js';


function listen(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen({ port, host: '0.0.0.0' }, () => resolve(server));
  });
}


test('ensureRuntimePorts shifts occupied default ports and syncs dependent env values', async () => {
  const home = mkdtempSync(join(tmpdir(), 'graphpilot-test-'));
  const previousHome = process.env.GRAPHPILOT_HOME;
  process.env.GRAPHPILOT_HOME = home;

  const backendServer = await listen(8000);
  const frontendServer = await listen(3000);

  try {
    writeFileSync(
      getEnvFile(),
      [
        'BACKEND_PORT=8000',
        'FRONTEND_PORT=3000',
        'CORS_ORIGINS=http://localhost:3000',
        'VITE_API_URL=http://localhost:8000',
        '',
      ].join('\n'),
      'utf8'
    );

    const ports = await ensureRuntimePorts();
    assert.notEqual(ports.backendPort, 8000);
    assert.notEqual(ports.frontendPort, 3000);

    const envMap = readEnvMap();
    assert.equal(envMap.get('BACKEND_PORT'), String(ports.backendPort));
    assert.equal(envMap.get('FRONTEND_PORT'), String(ports.frontendPort));
    assert.equal(envMap.get('CORS_ORIGINS'), `http://localhost:${ports.frontendPort}`);
    assert.equal(envMap.get('VITE_API_URL'), `http://localhost:${ports.backendPort}`);
  } finally {
    backendServer.close();
    frontendServer.close();
    if (previousHome === undefined) {
      delete process.env.GRAPHPILOT_HOME;
    } else {
      process.env.GRAPHPILOT_HOME = previousHome;
    }
    rmSync(home, { recursive: true, force: true });
  }
});
