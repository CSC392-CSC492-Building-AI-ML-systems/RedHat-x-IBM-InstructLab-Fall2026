#!/usr/bin/env bash
# Runs the GradeAI model on Fir from this computer. Use it through npm:
#   npm run model:connect          start the model on Fir if needed, open the tunnel, grade (leave it open)
#   npm run model:start [-- 8]     only submit the model job (hours, default MODEL_HOURS or 4)
#   npm run model:status           is the job waiting, loading or ready?
#   npm run model:log              end of the model job's log on Fir
#   npm run model:stop             cancel the model job (frees your group's GPU time)
# You sign in to Fir (with MFA) once; later commands reuse that sign-in for up to 12 hours.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then echo "No .env yet. Run: npm run setup" >&2; exit 1; fi
set -a; source ./.env; set +a
if [[ -z "${FIR_USER:-}" ]]; then echo "Set FIR_USER in .env to your Alliance username (or run npm run setup)." >&2; exit 1; fi
FIR_HOST="${FIR_HOST:-fir.alliancecan.ca}"
APP_URL="http://127.0.0.1:${PORT:-8080}"
TUNNEL_PORT="${MODEL_TUNNEL_PORT:-18000}"
HOURS="${MODEL_HOURS:-4}"

mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
SSH=(ssh -o ControlMaster=auto -o ControlPath="$HOME/.ssh/gradeai-%C" -o ControlPersist=12h
     -o ServerAliveInterval=30 -o ServerAliveCountMax=3 "$FIR_USER@$FIR_HOST")

say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*"; }

signed_in() { "${SSH[@]}" -O check >/dev/null 2>&1; }
sign_in() {
  signed_in && return 0
  say "Signing in to $FIR_HOST as $FIR_USER (approve the MFA prompt)…"
  "${SSH[@]}" true
}
fir() { "${SSH[@]}" bash -l '~/gradeai/fir-ctl.sh' "$@"; }

when() { date -r "$1" '+%a %H:%M' 2>/dev/null || date -d "@$1" '+%a %H:%M' 2>/dev/null || echo "?"; }

# Reads the newest model job's state into STATE JOB NODE REASON READY MODEL_PORT MODEL_KEY MODEL_END JOB_MODEL.
read_info() {
  local out k v
  out="$(fir info)" || { say "Couldn't ask Fir about the model job. Is ~/gradeai set up there? (see README)"; return 1; }
  STATE=NONE JOB="" NODE="" REASON="" READY=0 MODEL_PORT="" MODEL_KEY="" MODEL_END="" JOB_MODEL=""
  while IFS='=' read -r k v; do
    case "$k" in
      STATE|JOB|NODE|REASON|READY|MODEL_PORT|MODEL_KEY|MODEL_END) printf -v "$k" '%s' "$v" ;;
      MODEL_NAME) JOB_MODEL="$v" ;;
    esac
  done <<<"$out"
}

submit() {
  local hours="${1:-$HOURS}" out
  out="$(fir start "$hours")"
  if [[ "$out" =~ EXISTING=([0-9]+) ]]; then say "Model job ${BASH_REMATCH[1]} is already on Fir."
  elif [[ "$out" =~ SUBMITTED=([0-9]+) ]]; then say "Submitted model job ${BASH_REMATCH[1]} for $hours h."
  else echo "$out"; return 1; fi
}

cmd_start() { sign_in; submit "${1:-}"; }

cmd_status() {
  sign_in; read_info
  case "$STATE" in
    NONE) echo "No GradeAI model job on Fir. Start one with: npm run model:connect" ;;
    PENDING) echo "Job $JOB is waiting for a GPU on Fir (${REASON:-queued})." ;;
    RUNNING)
      echo "Job $JOB is running on $NODE${MODEL_END:+ until $(when "$MODEL_END")}."
      if [[ "$READY" == 1 ]]; then echo "The model is ready."; else echo "The model is still loading (npm run model:log to watch)."; fi ;;
    *) echo "Job $JOB: $STATE" ;;
  esac
}

cmd_log() { sign_in; fir log "${1:-40}"; }
cmd_stop() { sign_in; fir stop; }

FORWARD=""
open_tunnel() {
  close_tunnel
  if [[ -f .model-tunnel ]]; then "${SSH[@]}" -O cancel -L "$(cat .model-tunnel)" >/dev/null 2>&1 || true; fi
  FORWARD="127.0.0.1:$TUNNEL_PORT:$NODE:$MODEL_PORT"
  if ! "${SSH[@]}" -O forward -L "$FORWARD" >/dev/null 2>&1; then
    say "Couldn't open the tunnel on port $TUNNEL_PORT. Is something else using it? Set MODEL_TUNNEL_PORT in .env."
    FORWARD=""; return 1
  fi
  echo "$FORWARD" > .model-tunnel
}
close_tunnel() {
  if [[ -n "$FORWARD" ]]; then "${SSH[@]}" -O cancel -L "$FORWARD" >/dev/null 2>&1 || true; FORWARD=""; rm -f .model-tunnel; fi
}

WPID=""
finish() {
  trap - INT TERM
  trap 'kill -KILL "$WPID" 2>/dev/null || true' INT
  if [[ -n "$WPID" ]] && kill -0 "$WPID" 2>/dev/null; then
    say "Stopping: finishing files in progress (Ctrl-C again to quit now; they return to the queue)…"
    kill -TERM "$WPID" 2>/dev/null || true
    wait "$WPID" 2>/dev/null || true
  fi
  close_tunnel
  if [[ "$STATE" == RUNNING ]]; then
    say "Disconnected. The model job keeps running on Fir${MODEL_END:+ until $(when "$MODEL_END")}: reconnect with npm run model:connect, or free the GPU with npm run model:stop."
  fi
  exit 0
}

cmd_connect() {
  if ! curl -sf -m 3 "$APP_URL/api/me" >/dev/null 2>&1; then
    say "Waiting for GradeAI at $APP_URL. Start it in another terminal with: npm start"
    until curl -sf -m 3 "$APP_URL/api/me" >/dev/null 2>&1; do sleep 3; done
  fi
  sign_in
  read_info
  if [[ "$STATE" == NONE ]]; then
    local answer=y
    if [[ -t 0 ]]; then read -r -p "No model job is running on Fir. Start one for $HOURS hours? [Y/n] " answer || true; fi
    if [[ "$answer" =~ ^[Nn] ]]; then echo "Okay. Files wait in GradeAI until the model connects."; exit 0; fi
    submit "$HOURS"
    sleep 5; read_info
  fi

  local last=""
  while ! [[ "$STATE" == RUNNING && -n "$MODEL_PORT" ]]; do
    case "$STATE" in
      PENDING) [[ "$last" == PENDING ]] || say "Job $JOB is waiting for a GPU on Fir (${REASON:-queued}). This can take a while; files wait in GradeAI meanwhile." ;;
      RUNNING) [[ "$last" == RUNNING ]] || say "Job $JOB started on $NODE; preparing the model…" ;;
      NONE) say "The model job ended before it was ready. See what happened with: npm run model:log"; exit 1 ;;
      *) say "Job $JOB is $STATE." ;;
    esac
    last="$STATE"
    sleep 20; read_info
  done

  open_tunnel
  say "Tunnel open: model job $JOB on $NODE${MODEL_END:+ (ends $(when "$MODEL_END"))}."
  trap finish INT TERM

  GRADEAI_URL="$APP_URL" GRADEAI_WORKER_TOKEN="${WORKER_TOKEN:-}" \
  VLLM_URL="http://127.0.0.1:$TUNNEL_PORT/v1" VLLM_API_KEY="$MODEL_KEY" MODEL_NAME="${JOB_MODEL:-gradeai}" \
  FIR_JOB_ID="$JOB" FIR_NODE="$NODE" FIR_JOB_END="$MODEL_END" \
    python3 scripts/gradeai_worker.py &
  WPID=$!

  # Keep the tunnel alive: after the laptop sleeps or the network changes, sign in again.
  # Every 2 minutes, also check that the job is still running (cancelled, crashed or out of time).
  local ticks=0
  while kill -0 "$WPID" 2>/dev/null; do
    sleep 15 & wait $! || true
    kill -0 "$WPID" 2>/dev/null || break
    ticks=$((ticks + 1))
    if signed_in && (( ticks % 8 == 0 )) && read_info; then
      if ! [[ "$STATE" == RUNNING && "127.0.0.1:$TUNNEL_PORT:$NODE:$MODEL_PORT" == "$FORWARD" ]]; then
        say "The model job on Fir has ended. Start a new one with: npm run model:connect"
        break
      fi
    fi
    if ! signed_in; then
      say "Lost the connection to Fir (laptop slept or the network changed). Signing in again…"
      until "${SSH[@]}" true; do say "Couldn't reach Fir; trying again in 30 s (Ctrl-C to stop)."; sleep 30; done
      read_info || continue
      if [[ "$STATE" == RUNNING && -n "$MODEL_PORT" && "127.0.0.1:$TUNNEL_PORT:$NODE:$MODEL_PORT" == "$FORWARD" ]]; then
        FORWARD=""; open_tunnel && say "Reconnected. Grading resumes."
      else
        say "The model job on Fir has ended. Start a new one with: npm run model:connect"
        break
      fi
    fi
  done
  finish
}

case "${1:-}" in
  connect) cmd_connect ;;
  start) cmd_start "${2:-}" ;;
  status) cmd_status ;;
  log) cmd_log "${2:-}" ;;
  stop) cmd_stop ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
