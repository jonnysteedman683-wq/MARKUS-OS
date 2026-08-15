#!/usr/bin/env bash
# MARKUS OS Cron Runner — Entry Point
# Launches the hybrid cron agent daemon (additive; does NOT touch live cron scripts)
# Usage: ./markus_cron_runner.sh [-d | --daemon]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKUS_DIR="$(dirname "$SCRIPT_DIR")"

cd "$MARKUS_DIR"

if [ -f "markus_server.py" ]; then
  echo "Ensuring MARKUS server is available..."
  # Do NOT start; assume server is already running or will be started by Electron wrapper.
fi

if [ ! -d "hive-core" ]; then
  mkdir -p hive-core
fi

echo "Launching MARKUS Hybrid Cron Agent..."

if [ "$1" == "--single" ]; then
  python "$SCRIPT_DIR/markus_cron_agent.py" --single
else
  python "$SCRIPT_DIR/markus_cron_agent.py" --daemon
fi
