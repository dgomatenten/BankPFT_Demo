#!/usr/bin/env bash
# ──────────────────────────────────────────────────────
#  BankPFT — Application Startup Script
#  Usage:
#    ./start.sh              # development server (default)
#    ./start.sh dev          # development server (Flask debug)
#    ./start.sh prod         # production server (Gunicorn)
#    ./start.sh docker       # build & run via Docker Compose
#    ./start.sh stop         # stop a running Gunicorn process
# ──────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
PID_FILE="$SCRIPT_DIR/bankpft.pid"
LOG_FILE="$SCRIPT_DIR/bankpft.log"
BIND_ADDR="0.0.0.0:5000"
MODE="${1:-dev}"

# ── Colour helpers ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[BankPFT]${NC} $*"; }
success() { echo -e "${GREEN}[BankPFT]${NC} $*"; }
warn()    { echo -e "${YELLOW}[BankPFT]${NC} $*"; }
error()   { echo -e "${RED}[BankPFT]${NC} $*" >&2; }

# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────
activate_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        info "Creating virtual environment at $VENV_DIR ..."
        python3 -m venv "$VENV_DIR"
        success "Virtual environment created."
    fi
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    info "Activated virtual environment: $VENV_DIR"
}

install_deps() {
    if ! pip show flask > /dev/null 2>&1; then
        info "Installing dependencies from requirements.txt ..."
        pip install --quiet -r requirements.txt
        success "Dependencies installed."
    else
        info "Dependencies already installed."
    fi
}

ensure_instance_dir() {
    mkdir -p "$SCRIPT_DIR/instance"
    mkdir -p "$SCRIPT_DIR/uploads"
}

# ──────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────
cmd_dev() {
    activate_venv
    install_deps
    ensure_instance_dir
    success "Starting Flask development server on http://localhost:5000"
    info  "Press Ctrl+C to stop."
    echo ""
    FLASK_ENV=development FLASK_DEBUG=1 python run.py
}

cmd_prod() {
    activate_venv
    install_deps
    ensure_instance_dir

    if ! command -v gunicorn > /dev/null 2>&1; then
        error "Gunicorn not found. Run:  pip install gunicorn"
        exit 1
    fi

    if [[ -f "$PID_FILE" ]]; then
        OLD_PID=$(<"$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            warn "BankPFT is already running (PID $OLD_PID). Use './start.sh stop' first."
            exit 1
        fi
    fi

    WORKERS="${WORKERS:-4}"
    info "Starting Gunicorn (workers=$WORKERS) on http://$BIND_ADDR"
    info "Logs → $LOG_FILE   PID  → $PID_FILE"

    gunicorn \
        --bind "$BIND_ADDR" \
        --workers "$WORKERS" \
        --timeout 120 \
        --daemon \
        --pid "$PID_FILE" \
        --access-logfile "$LOG_FILE" \
        --error-logfile "$LOG_FILE" \
        "run:application"

    sleep 1
    if [[ -f "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
        success "BankPFT started in background (PID $(<"$PID_FILE"))."
        success "Open http://localhost:5000 in your browser."
    else
        error "Gunicorn failed to start. Check $LOG_FILE for details."
        exit 1
    fi
}

cmd_stop() {
    if [[ ! -f "$PID_FILE" ]]; then
        warn "No PID file found. BankPFT may not be running."
        exit 0
    fi
    PID=$(<"$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        rm -f "$PID_FILE"
        success "BankPFT stopped (PID $PID)."
    else
        warn "Process $PID is not running. Removing stale PID file."
        rm -f "$PID_FILE"
    fi
}

cmd_docker() {
    if ! command -v docker > /dev/null 2>&1; then
        error "Docker not found. Install Docker Desktop or Docker Engine first."
        exit 1
    fi
    if ! command -v docker compose > /dev/null 2>&1; then
        error "docker compose not found. Ensure Docker Compose v2 is installed."
        exit 1
    fi
    info "Building and starting BankPFT via Docker Compose ..."
    docker compose up --build
}

# ──────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────
case "$MODE" in
    dev|development)  cmd_dev   ;;
    prod|production)  cmd_prod  ;;
    stop)             cmd_stop  ;;
    docker)           cmd_docker ;;
    *)
        error "Unknown mode: '$MODE'"
        echo ""
        echo "Usage: $0 [dev|prod|stop|docker]"
        echo "  dev     Flask debug server  (default)"
        echo "  prod    Gunicorn daemon"
        echo "  stop    Stop Gunicorn daemon"
        echo "  docker  Docker Compose"
        exit 1
        ;;
esac
