#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';


const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const repoRoot = resolve(__dirname, '..', '..');
const composeFile = resolve(repoRoot, 'docker-compose.yml');
const smokeScript = resolve(repoRoot, 'scripts', 'smoke-backend.ps1');


function printHelp() {
  console.log(`GraphPilot CLI

Usage:
  graphpilot doctor      Check local prerequisites
  graphpilot up          Start local stack with docker compose
  graphpilot down        Stop local stack
  graphpilot logs        Follow docker compose logs
  graphpilot smoke       Run local backend smoke script
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


function doctor() {
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
      label: 'docker-compose.yml',
      ok: existsSync(composeFile),
      fail: 'docker-compose.yml was not found next to the packaged stack.',
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


function up() {
  run('docker', ['compose', '-f', composeFile, 'up', '-d']);
}


function down() {
  run('docker', ['compose', '-f', composeFile, 'down']);
}


function logs() {
  run('docker', ['compose', '-f', composeFile, 'logs', '-f']);
}


function smoke() {
  if (process.platform !== 'win32') {
    console.error('graphpilot smoke currently targets PowerShell on Windows hosts only.');
    process.exit(1);
  }

  run('powershell', ['-ExecutionPolicy', 'Bypass', '-File', smokeScript]);
}


const command = process.argv[2] || 'help';

switch (command) {
  case 'doctor':
    doctor();
    break;
  case 'up':
    up();
    break;
  case 'down':
    down();
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
