#!/usr/bin/env bash
# Restore the Frappe site from a backup set made by scripts/backup.sh.
# DESTRUCTIVE: replaces the site's database and files.
#
#   scripts/restore.sh --from backups/<timestamp> [--target compose|vm] (--yes | --dry-run)
#
# COMPOSE_PROJECT=<name> targets another compose project (used by tests/gate.sh).
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET=compose
FROM=""
YES=0
DRY_RUN=0
# The site name has one home: ansible/group_vars/all.yml (SITE_NAME overrides).
SITE=${SITE_NAME:-$(sed -n 's/^site_name: *//p' ansible/group_vars/all.yml)}
DB_ROOT_PASSWORD=${DB_ROOT_PASSWORD:-frappe}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM=${2%/}; shift 2 ;;
    --target) TARGET=$2; shift 2 ;;
    --yes) YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# The set must be inside ./backups: that directory is what the container
# (/workspace/backups) and the VM (/vagrant/backups) can see.
[[ "$FROM" == backups/* && -d "$FROM" ]] || { echo "--from must be an existing backups/<timestamp> directory" >&2; exit 2; }
(( YES || DRY_RUN )) || { echo "Refusing to overwrite the site without --yes (or use --dry-run)" >&2; exit 2; }

pick() {  # the single file in $FROM whose name ends in $1 (and not in $2)
  local matches
  mapfile -t matches < <(find "$FROM" -maxdepth 1 -type f -name "*$1" ${2:+-not -name "*$2"} -printf '%f\n')
  [[ ${#matches[@]} -eq 1 ]] || { echo "expected exactly one *$1 in $FROM" >&2; exit 1; }
  echo "${matches[0]}"
}
DB=$(pick -database.sql.gz)
PUBLIC=$(pick -files.tar -private-files.tar)   # frappe names public files "-files.tar"
PRIVATE=$(pick -private-files.tar)

run() {
  if (( DRY_RUN )); then printf '[dry-run]'; printf ' %q' "$@"; echo; else "$@"; fi
}

case "$TARGET" in
  compose) ROOT=/workspace ;;
  vm) ROOT=/vagrant ;;
  *) echo "--target must be compose or vm" >&2; exit 2 ;;
esac
DIR="$ROOT/$FROM"
RESTORE_ARGS=(--site "$SITE" restore "$DIR/$DB"
  --with-public-files "$DIR/$PUBLIC" --with-private-files "$DIR/$PRIVATE"
  --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" --non-interactive)
MIGRATE_ARGS=(--site "$SITE" migrate)

if [[ "$TARGET" == compose ]]; then
  PC=(podman compose ${COMPOSE_PROJECT:+-p "$COMPOSE_PROJECT"} exec -u frappe frappe bench)
  run "${PC[@]}" "${RESTORE_ARGS[@]}"
  run "${PC[@]}" "${MIGRATE_ARGS[@]}"
else
  # The command crosses a remote shell: quote every argument (%q), and call
  # bench by path rather than relying on the login shell's PATH.
  printf -v R ' %q' "${RESTORE_ARGS[@]}"
  printf -v M ' %q' "${MIGRATE_ARGS[@]}"
  run vagrant ssh -c "cd ~/frappe-bench && ~/.local/bin/bench$R && ~/.local/bin/bench$M"
fi
(( DRY_RUN )) && echo "[dry-run] nothing was changed" || echo "Restored $SITE from $FROM"
