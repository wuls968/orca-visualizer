#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PID_FILE="$ROOT_DIR/.streamlit_app.pid"
PORT_FILE="$ROOT_DIR/.streamlit_app.port"
LOG_FILE="$ROOT_DIR/.streamlit_app.log"
APP_SCRIPT="$ROOT_DIR/orca_viz/streamlit_app.py"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

python - <<'PY'
import importlib.util
import subprocess
import sys

required = ["streamlit", "orca_viz"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "."])
PY

is_pid_alive() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

source_tree_changed_since_pid_file() {
  local marker_file="$1"
  [ -f "$marker_file" ] || return 0
  find "$ROOT_DIR/orca_viz" -type f -name '*.py' -newer "$marker_file" -print -quit | grep -q .
}

port_is_listening() {
  python - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
for host in ("127.0.0.1", "localhost"):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            raise SystemExit(0)
    except OSError:
        continue
raise SystemExit(1)
PY
}

pick_free_port() {
  python - <<'PY'
import socket

for port in range(8501, 8601):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        raise SystemExit(0)
raise SystemExit("No free port found between 8501 and 8600.")
PY
}

open_browser() {
  local url="$1"
  if [ "${ORCA_VIZ_NO_OPEN:-0}" = "1" ]; then
    return 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
  fi
}

if [ -f "$PID_FILE" ] && [ -f "$PORT_FILE" ]; then
  existing_pid="$(tr -d '[:space:]' < "$PID_FILE")"
  existing_port="$(tr -d '[:space:]' < "$PORT_FILE")"
  if [ -n "$existing_pid" ] && [ -n "$existing_port" ] && is_pid_alive "$existing_pid" && port_is_listening "$existing_port"; then
    if source_tree_changed_since_pid_file "$PID_FILE" || [ "$APP_SCRIPT" -nt "$PID_FILE" ] || [ "$ROOT_DIR/app.py" -nt "$PID_FILE" ]; then
      echo "Detected newer source files. Restarting ORCA Visualizer..."
      kill "$existing_pid" >/dev/null 2>&1 || true
      sleep 1
      if is_pid_alive "$existing_pid"; then
        kill -9 "$existing_pid" >/dev/null 2>&1 || true
      fi
      rm -f "$PID_FILE" "$PORT_FILE"
    else
    url="http://localhost:${existing_port}"
    echo "ORCA Visualizer is already running at ${url}"
    open_browser "$url"
    exit 0
    fi
  fi
fi

port="$(pick_free_port)"
url="http://localhost:${port}"
rm -f "$PID_FILE" "$PORT_FILE"
: > "$LOG_FILE"

nohup python -m streamlit run "$APP_SCRIPT" --server.headless true --server.port "$port" --browser.gatherUsageStats false >"$LOG_FILE" 2>&1 &
app_pid=$!
disown "$app_pid" >/dev/null 2>&1 || true
echo "$app_pid" > "$PID_FILE"
echo "$port" > "$PORT_FILE"

for _ in $(seq 1 30); do
  if ! is_pid_alive "$app_pid"; then
    break
  fi
  if port_is_listening "$port"; then
    echo "ORCA Visualizer is running at ${url}"
    echo "Log file: ${LOG_FILE}"
    open_browser "$url"
    exit 0
  fi
  sleep 1
done

echo "Failed to start ORCA Visualizer." >&2
echo "Recent log output:" >&2
tail -n 80 "$LOG_FILE" >&2 || true
rm -f "$PID_FILE" "$PORT_FILE"
exit 1
