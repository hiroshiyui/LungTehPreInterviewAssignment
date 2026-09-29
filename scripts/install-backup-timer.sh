#!/usr/bin/env bash
# Render, verify and (optionally) install the backup timer as systemd *user*
# units. This script NEVER enables or starts the timer: that stays a
# deliberate, manual step (see docs/ops.md).
#
#   scripts/install-backup-timer.sh [--target compose|vm]            # dry run (default)
#   scripts/install-backup-timer.sh [--target compose|vm] --install  # copy units + daemon-reload
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET=compose
INSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET=$2; shift 2 ;;
    --install) INSTALL=1; shift ;;
    --dry-run) INSTALL=0; shift ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$TARGET" == compose || "$TARGET" == vm ]] || { echo "--target must be compose or vm" >&2; exit 2; }

REPO_DIR=$(pwd)
RENDER_DIR=$(mktemp -d)
trap 'rm -rf "$RENDER_DIR"' EXIT

# Escape the path twice: systemd treats "%" as a specifier (so "%" -> "%%"),
# and sed treats "\", "&" and the "#" delimiter specially in a replacement.
UNIT_REPO_DIR=${REPO_DIR//%/%%}
SED_REPO_DIR=$(printf '%s' "$UNIT_REPO_DIR" | sed 's/[\\&#]/\\&/g')
for unit in frappe-backup.service frappe-backup.timer; do
  sed -e "s#@REPO_DIR@#$SED_REPO_DIR#g" -e "s#@TARGET@#$TARGET#g" \
    "ops/systemd/$unit.in" > "$RENDER_DIR/$unit"
done

echo "== Rendered units"
for unit in "$RENDER_DIR"/*; do echo "--- $(basename "$unit")"; cat "$unit"; done

echo "== systemd-analyze verify"
systemd-analyze --user verify "$RENDER_DIR/frappe-backup.service" "$RENDER_DIR/frappe-backup.timer"
echo "units OK"

echo "== Next trigger times (if it were enabled)"
systemd-analyze calendar --iterations=3 '*-*-* 03:00:00' | sed -n '/Next elapse/,$p'

echo "== What the service would run"
scripts/backup.sh --target "$TARGET" --dry-run

UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
if (( INSTALL )); then
  mkdir -p "$UNIT_DIR"
  cp "$RENDER_DIR/frappe-backup.service" "$RENDER_DIR/frappe-backup.timer" "$UNIT_DIR/"
  systemctl --user daemon-reload
  echo "Installed into $UNIT_DIR (NOT enabled)."
else
  echo "Dry run: nothing was installed. Re-run with --install to copy the units into $UNIT_DIR."
fi
echo "To enable the schedule yourself:  systemctl --user enable --now frappe-backup.timer"
