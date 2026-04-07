#!/usr/bin/env bash
# ──────────────────────────────────────────────────────
#  BankPFT — Application Startup Script
#  Usage:
#    ./start.sh              # dev server with PostgreSQL (default)
#    ./start.sh dev          # dev server with PostgreSQL (Flask debug)
#    ./start.sh pg           # start PostgreSQL container then Flask
#    ./start.sh db           # start PostgreSQL container only
#    ./start.sh prod         # production server (Gunicorn + PostgreSQL)
#    ./start.sh docker       # build & run full stack via Docker Compose
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

# ── PostgreSQL connection (can be overridden via environment) ──
PG_URL="${DATABASE_URL:-postgresql://bankpft:bankpft_dev@localhost:5432/bankpft}"

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
    info  "Database → $PG_URL"
    info  "Press Ctrl+C to stop."
    echo ""
    DATABASE_URL="$PG_URL" FLASK_ENV=development FLASK_DEBUG=1 python run.py
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
    info "Database → $PG_URL"
    info "Logs → $LOG_FILE   PID  → $PID_FILE"

    DATABASE_URL="$PG_URL" gunicorn \
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

cmd_db() {
    if ! command -v docker > /dev/null 2>&1; then
        error "Docker not found. Install Docker Desktop or Docker Engine first."
        exit 1
    fi

    # Check if the db container is already running
    if docker ps --format '{{.Names}}' | grep -q '^bankpft-db-1$'; then
        success "PostgreSQL container (bankpft-db-1) is already running."
        return 0
    fi

    info "Starting PostgreSQL container via Docker Compose ..."
    docker compose up -d db

    # Wait for healthy status (up to 30 s)
    info "Waiting for PostgreSQL to be ready ..."
    local attempts=0
    until docker compose exec -T db pg_isready -U bankpft -q 2>/dev/null; do
        attempts=$((attempts + 1))
        if [[ $attempts -ge 30 ]]; then
            error "PostgreSQL did not become ready within 30 seconds."
            error "Check logs with: docker compose logs db"
            exit 1
        fi
        sleep 1
    done

    success "PostgreSQL is ready on localhost:5432  (db=bankpft, user=bankpft)"
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

cmd_pg() {
    cmd_db
    cmd_dev
}

# ──────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────
case "$MODE" in
    dev|development)  cmd_dev   ;;
    pg)               cmd_pg    ;;
    db|postgres)      cmd_db    ;;
    prod|production)  cmd_prod  ;;
    stop)             cmd_stop  ;;
    docker)           cmd_docker ;;
    *)
        error "Unknown mode: '$MODE'"
        echo ""
        echo "Usage: $0 [dev|pg|db|prod|stop|docker]"
        echo "  dev     Flask debug server with PostgreSQL  (default)"
        echo "  pg      Start PostgreSQL container then Flask dev server"
        echo "  db      Start PostgreSQL Docker container only"
        echo "  prod    Gunicorn daemon with PostgreSQL"
        echo "  stop    Stop Gunicorn daemon"
        echo "  docker  Full stack via Docker Compose"
        exit 1
        ;;
esac
