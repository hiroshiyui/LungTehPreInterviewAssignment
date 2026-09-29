#!/usr/bin/env bash
# Install the pinned ansible-core (ansible/requirements.txt) into /opt/ansible.
# Used by the Vagrant VM, the test container and the compose image.
# Idempotent: does nothing if the pinned version is already installed.
set -euo pipefail

REQUIREMENTS="${ANSIBLE_REQUIREMENTS:-/vagrant/ansible/requirements.txt}"
VENV=/opt/ansible
WANTED=$(sed -n 's/^ansible-core==//p' "$REQUIREMENTS")

if [[ -x "$VENV/bin/ansible-playbook" ]] &&
   [[ "$("$VENV/bin/python" -c 'import ansible.release as r; print(r.__version__)')" == "$WANTED" ]]; then
  echo "ansible-core $WANTED already installed"
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends python3-venv python3-apt

python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$REQUIREMENTS"

for bin in ansible ansible-playbook ansible-galaxy; do
  ln -sf "$VENV/bin/$bin" "/usr/local/bin/$bin"
done

"$VENV/bin/ansible-playbook" --version | head -1
