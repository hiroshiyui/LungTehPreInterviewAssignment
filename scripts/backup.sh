#!/usr/bin/env bash
# Back up the Frappe site: database + public/private files + site config.
#
#   scripts/backup.sh [--target compose|vm] [--keep N] [--dry-run]
#
#   --target   compose (default): the podman-compose stack in this directory
#              vm: the Vagrant VM
#   --keep N   keep the newest N backup sets in ./backups (default 14)
#   --dry-run  print what would run; change nothing
#
# COMPOSE_PROJECT=<name> targets another compose project (used by tests/gate.sh).
#
# `bench backup --backup-path` writes straight into ./backups/<timestamp>/
# through the bind mount (/workspace) or shared folder (/vagrant), so the
# backup lands on the host, outside the volumes/VM it protects.
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET=compose
KEEP=14
DRY_RUN=0
# The site name has one home: ansible/group_vars/all.yml (SITE_NAME overrides).
SITE=${SITE_NAME:-$(sed -n 's/^site_name: *//p' ansible/group_vars/all.yml)}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET=$2; shift 2 ;;
    --keep) KEEP=$2; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || { echo "--keep must be a positive integer" >&2; exit 2; }

run() {
  if (( DRY_RUN )); then printf '[dry-run]'; printf ' %q' "$@"; echo; else "$@"; fi
}

STAMP=$(date +%Y%m%d-%H%M%S)
BENCH_ARGS=(--site "$SITE" backup --with-files --backup-path)

case "$TARGET" in
  compose)
    run podman compose ${COMPOSE_PROJECT:+-p "$COMPOSE_PROJECT"} exec -u frappe frappe bench "${BENCH_ARGS[@]}" "/workspace/backups/$STAMP"
    ;;
  vm)
    # The command crosses a remote shell: quote every argument (%q), and call
    # bench by path rather than relying on the login shell's PATH.
    printf -v REMOTE_ARGS ' %q' "${BENCH_ARGS[@]}" "/vagrant/backups/$STAMP"
    run vagrant ssh -c "cd ~/frappe-bench && ~/.local/bin/bench$REMOTE_ARGS"
    ;;
  *) echo "--target must be compose or vm" >&2; exit 2 ;;
esac

# Retention: backup directories are named by timestamp, so name order is age order.
mapfile -t OLD < <(find backups -mindepth 1 -maxdepth 1 -type d -name '20*' 2>/dev/null | sort | head -n "-$KEEP")
if (( ${#OLD[@]} )); then
  run rm -rf -- "${OLD[@]}"
fi

if (( DRY_RUN )); then
  echo "[dry-run] would keep the newest $KEEP set(s) in $(pwd)/backups; nothing was changed"
else
  echo "Backup written to backups/$STAMP"
fi
