#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { randomBytes } from 'node:crypto';
import net from 'node:net';


const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const packageRoot = resolve(__dirname, '..');
const templatesDir = resolve(packageRoot, 'templates');
const defaultAppDir = join(homedir(), '.graphpilot');


function getAppDir() {
  return process.env.GRAPHPILOT_HOME || defaultAppDir;
}


function getComposeFile() {
  return join(getAppDir(), 'docker-compose.yml');
}


function getEnvFile() {
  return join(getAppDir(), '.env');
}


function getEnvExampleFile() {
  return join(getAppDir(), '.env.example');
}


function readEnvMap() {
  const envFile = getEnvFile();
  if (!existsSync(envFile)) {
    return new Map();
  }

  const content = readFileSync(envFile, 'utf8');
  const lines = content.split(/\r?\n/);
  const map = new Map();

  for (const line of lines) {
    if (!line || line.trim().startsWith('#')) continue;
    const idx = line.indexOf('=');
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1);
    map.set(key, value);
  }

  return map;
}


function updateEnvValues(values) {
  const envFile = getEnvFile();
  const current = existsSync(envFile) ? readFileSync(envFile, 'utf8') : '';
  const lines = current ? current.split(/\r?\n/) : [];
  const pending = new Map(Object.entries(values));
  const nextLines = [];

  for (const line of lines) {
    const idx = line.indexOf('=');
    if (idx === -1) {
      nextLines.push(line);
      continue;
    }

    const key = line.slice(0, idx).trim();
    if (pending.has(key)) {
      nextLines.push(`${key}=${pending.get(key)}`);
      pending.delete(key);
    } else {
      nextLines.push(line);
    }
  }

  for (const [key, value] of pending.entries()) {
    nextLines.push(`${key}=${value}`);
  }

  writeFileSync(envFile, `${nextLines.filter((line) => line !== undefined).join('\n')}\n`, 'utf8');
}


function canListen(port) {
  return new Promise((resolvePort) => {
    const server = net.createServer();
    server.unref();
    server.on('error', () => resolvePort(false));
    server.listen({ port, host: '0.0.0.0' }, () => {
      server.close(() => resolvePort(true));
    });
  });
}


async function findAvailablePort(startPort) {
  let port = startPort;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    // eslint-disable-next-line no-await-in-loop
    const available = await canListen(port);
    if (available) {
      return port;
    }
    port += 1;
  }

  throw new Error(`Could not find an available host port starting from ${startPort}`);
}


async function ensureRuntimePorts() {
  const composeFile = getComposeFile();
  const envMap = readEnvMap();
  const backendPort = Number(envMap.get('BACKEND_PORT') || '8000');
  const frontendPort = Number(envMap.get('FRONTEND_PORT') || '3000');

  if (existsSync(composeFile) && hasRunningStack(composeFile)) {
    return { backendPort, frontendPort };
  }

  const nextBackendPort = await findAvailablePort(backendPort);
  const nextFrontendPort = await findAvailablePort(frontendPort);

  const updates = {};
  const currentCors = envMap.get('CORS_ORIGINS') || '';
  const currentApiUrl = envMap.get('VITE_API_URL') || '';
  const oldCors = `http://localhost:${frontendPort}`;
  const oldApiUrl = `http://localhost:${backendPort}`;

  if (nextBackendPort !== backendPort) {
    updates.BACKEND_PORT = String(nextBackendPort);
    if (currentApiUrl === oldApiUrl) {
      updates.VITE_API_URL = `http://localhost:${nextBackendPort}`;
    }
  }
  if (nextFrontendPort !== frontendPort) {
    updates.FRONTEND_PORT = String(nextFrontendPort);
    if (currentCors === oldCors) {
      updates.CORS_ORIGINS = `http://localhost:${nextFrontendPort}`;
    }
  }
  if (Object.keys(updates).length > 0) {
    updateEnvValues(updates);
  }

  return {
    backendPort: nextBackendPort,
    frontendPort: nextFrontendPort,
  };
}


function printHelp() {
  console.log(`GraphPilot CLI

Usage:
  graphpilot doctor      Check local prerequisites
  graphpilot init        Initialize local GraphPilot runtime files
  graphpilot up          Start local stack with docker compose
  graphpilot status      Show local stack container status
  graphpilot down        Stop local stack
  graphpilot reset       Stop local stack and remove local Docker volumes
  graphpilot logs        Follow docker compose logs
  graphpilot smoke       Run packaged local smoke check
  graphpilot help        Show this help
`);
}


function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    shell: process.platform === 'win32',
    ...options,
  });

  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }

  process.exit(result.status ?? 1);
}


function commandExists(command, args = ['--version']) {
  const result = spawnSync(command, args, {
    stdio: 'ignore',
    shell: process.platform === 'win32',
  });
  return result.status === 0;
}


function hasRunningStack(composeFile) {
  const result = spawnSync('docker', ['compose', '-f', composeFile, 'ps', '--services', '--status', 'running'], {
    encoding: 'utf8',
    shell: process.platform === 'win32',
  });
  if (result.status !== 0) return false;
  return result.stdout.trim().length > 0;
}


function ensureInitialized() {
  const composeFile = getComposeFile();
  if (!existsSync(composeFile)) {
    console.error("GraphPilot is not initialized yet. Run 'graphpilot init' first.");
    process.exit(1);
  }
  return composeFile;
}


function doctor() {
  const composeFile = getComposeFile();
  const checks = [
    {
      label: 'docker',
      ok: commandExists('docker'),
      fail: 'Docker is not available in PATH.',
    },
    {
      label: 'docker compose',
      ok: commandExists('docker', ['compose', 'version']),
      fail: 'Docker Compose plugin is not available.',
    },
    {
      label: 'graphpilot runtime',
      ok: existsSync(composeFile),
      fail: `Run 'graphpilot init' first. Expected runtime at ${composeFile}`,
    },
  ];

  let hasFailure = false;
  for (const check of checks) {
    if (check.ok) {
      console.log(`[ok] ${check.label}`);
    } else {
      hasFailure = true;
      console.log(`[fail] ${check.label} - ${check.fail}`);
    }
  }

  if (!hasFailure) {
    console.log('GraphPilot local prerequisites look good.');
  }

  process.exit(hasFailure ? 1 : 0);
}


function init() {
  const appDir = getAppDir();
  const composeFile = getComposeFile();
  const envFile = getEnvFile();
  const envExampleFile = getEnvExampleFile();

  mkdirSync(appDir, { recursive: true });

  if (!existsSync(composeFile)) {
    copyFileSync(join(templatesDir, 'docker-compose.yml'), composeFile);
  }

  if (!existsSync(envExampleFile)) {
    copyFileSync(join(templatesDir, '.env.example'), envExampleFile);
  }

  if (!existsSync(envFile)) {
    copyFileSync(join(templatesDir, '.env.example'), envFile);

    const defaultJwtSecret = 'dev-secret-change-in-production';
    const generatedSecret = randomBytes(32).toString('hex');

    try {
      const currentEnv = readFileSync(envFile, 'utf8');
      writeFileSync(
        envFile,
        currentEnv.replace(defaultJwtSecret, generatedSecret),
        'utf8'
      );
    } catch (_error) {
      console.warn('Failed to auto-generate JWT secret; please update JWT_SECRET in your .env file.');
    }
  }

  console.log(`GraphPilot runtime initialized at ${appDir}`);
  console.log(`Edit ${envFile} if you need to customize local settings.`);
}


async function up() {
  const composeFile = ensureInitialized();
  const ports = await ensureRuntimePorts();
  const result = spawnSync('docker', ['compose', '-f', composeFile, 'up', '-d'], {
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });

  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }

  if ((result.status ?? 1) !== 0) {
    process.exit(result.status ?? 1);
  }

  console.log('GraphPilot stack is starting.');
  console.log(`Frontend: http://localhost:${ports.frontendPort}`);
  console.log(`Backend API: http://localhost:${ports.backendPort}`);
  console.log(`Health: http://localhost:${ports.backendPort}/health`);
  console.log("Use 'graphpilot status' to inspect containers or 'graphpilot logs' to follow startup logs.");
}


function down() {
  const composeFile = ensureInitialized();
  run('docker', ['compose', '-f', composeFile, 'down']);
}


function status() {
  const composeFile = ensureInitialized();
  run('docker', ['compose', '-f', composeFile, 'ps']);
}


function reset() {
  const composeFile = ensureInitialized();
  run('docker', ['compose', '-f', composeFile, 'down', '-v']);
}


function logs() {
  const composeFile = ensureInitialized();
  run('docker', ['compose', '-f', composeFile, 'logs', '-f']);
}


function smoke() {
  const composeFile = ensureInitialized();

  const shell = process.platform === 'win32';
  const runCompose = (args, allowFailure = false) => {
    const result = spawnSync('docker', ['compose', '-f', composeFile, ...args], {
      stdio: 'inherit',
      shell,
    });

    if (result.error) {
      throw result.error;
    }

    const code = result.status ?? 1;
    if (!allowFailure && code !== 0) {
      throw new Error(`docker compose ${args.join(' ')} failed with exit code ${code}`);
    }
    return code;
  };

  const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

  const runSmoke = async () => {
    let exitCode = 0;

    try {
      const ports = await ensureRuntimePorts();
      runCompose(['up', '-d', 'db', 'backend']);

      for (let attempt = 0; attempt < 60; attempt += 1) {
        try {
          const res = await fetch(`http://localhost:${ports.backendPort}/health`);
          if (res.ok) {
            break;
          }
        } catch (_err) {
          // retry
        }

        if (attempt === 59) {
          throw new Error('Backend health check did not become ready in time.');
        }
        await sleep(1000);
      }

      const register = await fetch(`http://localhost:${ports.backendPort}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'graphpilot-smoke@test.com',
          password: 'securepass123',
          full_name: 'GraphPilot Smoke',
          tenant_name: 'GraphPilot Smoke Tenant',
        }),
      });
      if (!(register.status === 201 || register.status === 409)) {
        throw new Error(`Register failed with status ${register.status}`);
      }

      const login = await fetch(`http://localhost:${ports.backendPort}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'graphpilot-smoke@test.com',
          password: 'securepass123',
        }),
      });
      if (!login.ok) {
        throw new Error(`Login failed with status ${login.status}`);
      }

      const loginData = await login.json();
      const token = loginData.access_token;
      if (!token) {
        throw new Error('Login response missing access token');
      }

      const me = await fetch(`http://localhost:${ports.backendPort}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!me.ok) {
        throw new Error(`/auth/me failed with status ${me.status}`);
      }

      const health = await fetch(`http://localhost:${ports.backendPort}/health`);
      if (!health.ok) {
        throw new Error(`/health failed with status ${health.status}`);
      }

      console.log('GraphPilot smoke check passed.');
    } catch (err) {
      exitCode = 1;
      const message = err instanceof Error ? err.message : String(err);
      console.error(message);
      runCompose(['logs', 'backend'], true);
    } finally {
      runCompose(['down'], true);
    }

    process.exit(exitCode);
  };

  runSmoke();
}


async function main() {
  const command = process.argv[2] || 'help';
  switch (command) {
    case 'doctor':
      doctor();
      break;
    case 'init':
      init();
      break;
    case 'up':
      await up();
      break;
    case 'status':
      status();
      break;
    case 'down':
      down();
      break;
    case 'reset':
      reset();
      break;
    case 'logs':
      logs();
      break;
    case 'smoke':
      smoke();
      break;
    case 'help':
    default:
      printHelp();
      process.exit(command === 'help' ? 0 : 1);
  }
}


export {
  ensureRuntimePorts,
  getAppDir,
  getEnvFile,
  init,
  readEnvMap,
  updateEnvValues,
};


if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  });
}
