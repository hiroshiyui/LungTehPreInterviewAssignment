#!/usr/bin/env bash
# Run the same provisioning Vagrant runs (bootstrap + ansible_local), but in a
# systemd-enabled podman container. Useful for CI or hosts without VirtualBox.
#
#   tests/container/run.sh            # build image, (re)use container, provision
#   tests/container/run.sh --fresh    # destroy the container first
#   ANSIBLE_ARGS="--tags app" tests/container/run.sh
set -euo pipefail

cd "$(dirname "$0")/../.."
NAME=frappe-dev-test
IMAGE=localhost/frappe-dev-test:latest

if [[ "${1:-}" == "--fresh" ]]; then
  podman rm -f "$NAME" >/dev/null 2>&1 || true
fi

podman build -q -t "$IMAGE" tests/container >/dev/null

if ! podman container exists "$NAME"; then
  podman run -d --name "$NAME" --hostname frappe-dev \
    --systemd=always --user root --userns=keep-id:uid=1000,gid=1000 \
    -v "$PWD:/vagrant" -p 127.0.0.1:18000:8000 \
    "$IMAGE" >/dev/null
fi
podman start "$NAME" >/dev/null
# Let systemd finish booting first: the playbook manages services. "degraded"
# (some unit failed) still counts as booted, so ignore the exit status.
podman exec "$NAME" systemctl is-system-running --wait >/dev/null 2>&1 || true

podman exec "$NAME" bash /vagrant/scripts/bootstrap-ansible.sh

# shellcheck disable=SC2086
podman exec -w /vagrant/ansible -e ANSIBLE_FORCE_COLOR=1 "$NAME" \
  /opt/ansible/bin/ansible-playbook -i localhost, -c local \
  -e frappe_user=vagrant site.yml ${ANSIBLE_ARGS:-}

echo "Frappe is reachable at http://127.0.0.1:18000"
