#!/usr/bin/env bash
# The project gate: one command that says whether a change is safe to commit.
#
#   tests/gate.sh           full gate: static checks, a from-scratch build in the
#                           test container, then a second run that must report
#                           changed=0 (idempotency). ~8 min.
#   tests/gate.sh --quick   static checks + the app's unit tests in the running
#                           test container. ~1 min. Enough for app-only changes.
#   tests/gate.sh --compose static checks + the podman-compose variant: build,
#                           start, verify, then recreate every container and
#                           check that data and uploaded files survived.
#                           Uses its own project/ports; never touches your stack.
#
# Needs podman. vagrant and ansible-lint are used when installed.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
fail() { printf '\033[31mGATE FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

MODE=full
case "${1:-}" in
  --quick) MODE=quick ;;
  --compose) MODE=compose ;;
  "") ;;
  *) fail "unknown option: $1" ;;
esac
NAME=frappe-dev-test
SITE=$(sed -n 's/^site_name: *//p' ansible/group_vars/all.yml)   # its one home
LOG_DIR=$(mktemp -d)
trap 'rm -rf "$LOG_DIR"' EXIT

step "Static checks"
bash -n scripts/*.sh tests/*.sh tests/container/*.sh compose/*.sh || fail "shell syntax"
for f in $(find apps -name '*.json' -not -path '*/node_modules/*'); do
  python3 -m json.tool "$f" >/dev/null || fail "invalid JSON: $f"
done
if command -v vagrant >/dev/null; then
  vagrant validate --ignore-provider >/dev/null || fail "vagrant validate"
  echo "Vagrantfile OK"
fi
if podman compose version >/dev/null 2>&1; then
  podman compose config >/dev/null || fail "compose.yaml"
  echo "compose.yaml OK"
fi
if command -v ansible-lint >/dev/null; then
  (cd ansible && ansible-lint --nocolor site.yml </dev/null) || fail "ansible-lint"
fi

if [[ "$MODE" == quick ]]; then
  step "App unit tests (container $NAME)"
  podman container exists "$NAME" && [[ "$(podman inspect -f '{{.State.Running}}' "$NAME")" == true ]] \
    || fail "container $NAME is not running; run tests/container/run.sh first"
  podman exec -u vagrant -w /home/vagrant/frappe-bench \
    -e PATH=/home/vagrant/.local/bin:/usr/local/bin:/usr/bin:/bin -e LANG=C.UTF-8 "$NAME" \
    bench --site "$SITE" run-tests --app hr_cost || fail "unit tests"
elif [[ "$MODE" == compose ]]; then
  export FRAPPE_HOST_PORT=18080 FRAPPE_REALTIME_PORT=19000
  PC=(podman compose -p frappe-gate)
  URL=http://127.0.0.1:$FRAPPE_HOST_PORT
  trap '"${PC[@]}" down -v >/dev/null 2>&1 || true; rm -rf "$LOG_DIR"' EXIT
  wait_up() {
    for _ in $(seq 120); do
      curl -fsS "$URL/api/method/ping" 2>/dev/null | grep -q pong && return 0
      sleep 5
    done
    "${PC[@]}" logs frappe | tail -40; fail "site did not come up"
  }
  api() { curl -fsS -b "$LOG_DIR/cookies" -c "$LOG_DIR/cookies" "$@"; }

  step "podman compose: build and start (project frappe-gate)"
  "${PC[@]}" down -v >/dev/null 2>&1 || true
  "${PC[@]}" up -d --build || fail "compose up"
  wait_up

  step "Verify role inside the frappe container (API checks + unit tests)"
  "${PC[@]}" exec frappe bash -c 'cd /workspace/ansible && ansible-playbook -i localhost, -c local \
    -e @vars/container.yml -e site_name="$SITE_NAME" -e admin_password="$ADMIN_PASSWORD" \
    --tags verify site.yml' || fail "verify role"

  step "Storage: write data and a file, recreate all containers, read them back"
  api -X POST "$URL/api/method/login" -H 'Content-Type: application/json' \
    -d '{"usr":"Administrator","pwd":"admin"}' >/dev/null || fail "login"
  api -X POST "$URL/api/resource/Employee" -H 'Content-Type: application/json' \
    -d '{"employee_name":"Gate Persistence","date_of_joining":"2026-01-01","hourly_rate":123}' >/dev/null || fail "create employee"
  echo "gate-$$" > "$LOG_DIR/gate.txt"
  file_url=$(api -X POST "$URL/api/method/upload_file" -F "file=@$LOG_DIR/gate.txt" -F is_private=0 \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["message"]["file_url"])') || fail "upload file"

  "${PC[@]}" down >/dev/null || fail "compose down"          # containers gone, volumes kept
  "${PC[@]}" up -d || fail "compose up (recreate)"
  wait_up
  api -X POST "$URL/api/method/login" -H 'Content-Type: application/json' \
    -d '{"usr":"Administrator","pwd":"admin"}' >/dev/null || fail "login after recreate"
  api "$URL/api/resource/Employee?filters=%5B%5B%22employee_name%22%2C%22%3D%22%2C%22Gate%20Persistence%22%5D%5D" \
    | grep -q '"name"' || fail "database row lost after recreate"
  curl -fsS "$URL$file_url" | grep -qx "gate-$$" || fail "uploaded file lost after recreate"
  echo "database row and uploaded file survived container recreation"

  step "Backup and restore round trip"
  export COMPOSE_PROJECT=frappe-gate
  # --keep 1000: never prune the developer's own backup sets in ./backups
  set_dir=$(scripts/backup.sh --keep 1000 | sed -n 's/^Backup written to //p')
  [[ -n "$set_dir" && -d "$set_dir" ]] || fail "backup"
  trap '"${PC[@]}" down -v >/dev/null 2>&1 || true; rm -rf "$LOG_DIR" "$set_dir"' EXIT
  emp=$(api "$URL/api/resource/Employee?filters=%5B%5B%22employee_name%22%2C%22%3D%22%2C%22Gate%20Persistence%22%5D%5D" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["name"])')
  api -X DELETE "$URL/api/resource/Employee/$emp" >/dev/null || fail "delete employee"
  scripts/restore.sh --from "$set_dir" --yes || fail "restore"
  api -X POST "$URL/api/method/login" -H 'Content-Type: application/json' \
    -d '{"usr":"Administrator","pwd":"admin"}' >/dev/null || fail "login after restore"
  api "$URL/api/resource/Employee/$emp" | grep -q "Gate Persistence" || fail "deleted row not restored"
  curl -fsS "$URL$file_url" | grep -qx "gate-$$" || fail "file missing after restore"
  echo "deleted row and uploaded file came back from the backup"
else
  step "Fresh build (includes the verify role: API checks + unit tests)"
  tests/container/run.sh --fresh 2>&1 | tee "$LOG_DIR/fresh.log" || fail "fresh build"

  step "Idempotency: second run must change nothing"
  tests/container/run.sh 2>&1 | tee "$LOG_DIR/rerun.log" || fail "second run"
  recap=$(sed 's/\x1b\[[0-9;]*m//g' "$LOG_DIR/rerun.log" | grep -A1 'PLAY RECAP' | tail -1)
  [[ "$recap" =~ changed=0\  ]] || fail "not idempotent: $recap"
fi

printf '\n\033[32mGATE PASSED (%s)\033[0m\n' "$MODE"
