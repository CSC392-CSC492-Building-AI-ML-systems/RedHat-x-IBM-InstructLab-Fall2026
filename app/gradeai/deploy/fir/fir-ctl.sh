#!/bin/bash
# Runs on Fir. GradeAI on your laptop calls it over SSH (scripts/fir.sh); you can also run it here:
#   bash ~/gradeai/fir-ctl.sh start [hours]   submit the model job (default 4 h) unless one exists
#   bash ~/gradeai/fir-ctl.sh status          what the model job is doing
#   bash ~/gradeai/fir-ctl.sh log [lines]     end of the newest job's log
#   bash ~/gradeai/fir-ctl.sh stop            cancel the model job
#   bash ~/gradeai/fir-ctl.sh info            the same as status, for the laptop script
set -euo pipefail
G="${GRADEAI_HOME:-$HOME/gradeai}"
NAME=gradeai-serve

newest() { squeue -h -u "$USER" -n "$NAME" -o '%i|%T|%N|%r' 2>/dev/null | sort -t'|' -k1,1n | tail -n 1; }

case "${1:-status}" in
  start)
    hours="${2:-4}"
    if ! [[ "$hours" =~ ^[0-9]+$ ]] || (( hours < 1 || hours > 168 )); then
      echo "Hours must be a whole number from 1 to 168." >&2; exit 2
    fi
    cur="$(newest)"
    if [[ -n "$cur" ]]; then echo "EXISTING=${cur%%|*}"; exit 0; fi
    mkdir -p "$G/logs" "$G/jobs" && chmod 700 "$G/logs" "$G/jobs"
    for f in "$G"/jobs/*.env; do   # forget jobs that are gone
      [[ -e "$f" ]] || continue
      [[ -n "$(squeue -h -j "$(basename "$f" .env)" 2>/dev/null || true)" ]] || rm -f "$f"
    done
    cd "$G"
    out="$(sbatch --parsable --time="${hours}:00:00" --output="$G/logs/%x-%j.out" "$G/gradeai-serve.sbatch")"
    echo "SUBMITTED=${out%%;*}"
    ;;

  info|status)
    cur="$(newest)"
    if [[ -z "$cur" ]]; then
      if [[ "$1" == info ]]; then echo "STATE=NONE"; else echo "No GradeAI model job on Fir."; fi
      exit 0
    fi
    IFS='|' read -r job state node reason <<<"$cur"
    f="$G/jobs/$job.env"
    port=""; key=""; ready=0
    if [[ "$state" == RUNNING && -f "$f" ]]; then
      port="$(sed -n 's/^MODEL_PORT=//p' "$f")"; key="$(sed -n 's/^MODEL_KEY=//p' "$f")"
      if curl -sf -m 5 -H "Authorization: Bearer $key" "http://$node:$port/v1/models" >/dev/null 2>&1; then ready=1; fi
    fi
    if [[ "$1" == info ]]; then
      printf 'JOB=%s\nSTATE=%s\nNODE=%s\nREASON=%s\nREADY=%s\n' "$job" "$state" "$node" "$reason" "$ready"
      if [[ -n "$port" ]]; then cat "$f"; fi
    else
      echo "Job $job: $state${node:+ on $node}${reason:+ ($reason)}"
      if [[ "$state" == RUNNING ]]; then
        if (( ready )); then echo "Model is ready."; else echo "Model is loading (or check: bash $0 log)."; fi
      fi
      squeue -h -j "$job" -o 'Time used %M, time left %L' 2>/dev/null || true
    fi
    ;;

  log)
    last="$(ls -t "$G"/logs/"$NAME"-*.out 2>/dev/null | head -n 1 || true)"
    if [[ -z "$last" ]]; then echo "No model job logs yet in $G/logs."; exit 0; fi
    echo "== $last"; tail -n "${2:-40}" "$last"
    ;;

  stop)
    jobs="$(squeue -h -u "$USER" -n "$NAME" -o %i 2>/dev/null | tr '\n' ' ')"
    if [[ -z "${jobs// /}" ]]; then echo "No GradeAI model job to stop."; exit 0; fi
    scancel $jobs && echo "Cancelled model job(s): $jobs"
    ;;

  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
