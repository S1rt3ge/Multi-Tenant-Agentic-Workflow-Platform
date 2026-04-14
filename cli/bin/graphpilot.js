#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';


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


function printHelp() {
  console.log(`GraphPilot CLI

Usage:
  graphpilot doctor      Check local prerequisites
  graphpilot init        Initialize local GraphPilot runtime files
  graphpilot up          Start local stack with docker compose
  graphpilot down        Stop local stack
  graphpilot logs        Follow docker compose logs
  graphpilot smoke       Placeholder for future packaged smoke flow
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
  }

  console.log(`GraphPilot runtime initialized at ${appDir}`);
  console.log(`Edit ${envFile} if you need to customize local settings.`);
}


function up() {
  const composeFile = getComposeFile();
  if (!existsSync(composeFile)) {
    console.error("GraphPilot is not initialized yet. Run 'graphpilot init' first.");
    process.exit(1);
  }
  run('docker', ['compose', '-f', composeFile, 'up', '-d']);
}


function down() {
  const composeFile = getComposeFile();
  if (!existsSync(composeFile)) {
    console.error("GraphPilot is not initialized yet. Run 'graphpilot init' first.");
    process.exit(1);
  }
  run('docker', ['compose', '-f', composeFile, 'down']);
}


function logs() {
  const composeFile = getComposeFile();
  if (!existsSync(composeFile)) {
    console.error("GraphPilot is not initialized yet. Run 'graphpilot init' first.");
    process.exit(1);
  }
  run('docker', ['compose', '-f', composeFile, 'logs', '-f']);
}


function smoke() {
  console.error('graphpilot smoke is not packaged yet. Use CI smoke or repository smoke tooling for now.');
  process.exit(1);
}


const command = process.argv[2] || 'help';

switch (command) {
  case 'doctor':
    doctor();
    break;
  case 'init':
    init();
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
