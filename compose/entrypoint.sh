#!/usr/bin/env bash
# Start-up of the `frappe` compose service:
#   1. wait for MariaDB,
#   2. run the playbook's `site` and `app` roles (create the site on first
#      start, install/migrate the app, load demo data; idempotent),
#   3. hand over to `bench start` as the frappe user.
set -euo pipefail

SITE_DIR="/home/frappe/frappe-bench/sites/${SITE_NAME:?}"

echo "Waiting for MariaDB at ${DB_HOST:?}..."
until mariadb-admin ping -h "$DB_HOST" -uroot -p"${DB_ROOT_PASSWORD:?}" --silent 2>/dev/null; do
  sleep 2
done

# The site directory is a named volume; make sure the bench user owns it.
mkdir -p "$SITE_DIR"
chown frappe:frappe "$SITE_DIR"

cd /workspace/ansible
ansible-playbook -i localhost, -c local \
  -e @vars/container.yml \
  -e "site_name=$SITE_NAME" \
  -e "mariadb_root_password=$DB_ROOT_PASSWORD" \
  -e "admin_password=${ADMIN_PASSWORD:?}" \
  --tags site,app site.yml

cd /home/frappe/frappe-bench
exec runuser -u frappe -- env HOME=/home/frappe bench start
