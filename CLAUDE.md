# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A pre-interview assignment kept as a long-term **beginners' onboarding tutorial**:

- a reproducible **Frappe `develop`** dev environment;
- the custom app `apps/hr_cost`: Employee and Work Record DocTypes, plus the "Daily HR Cost" and "Monthly HR Cost" script reports.

There are two ways to run it, both built by the **same Ansible playbook**:

- **VirtualBox**: a VirtualBox VM (the `Vagrantfile`, `ansible_local`). This is what the assignment asks for.
- **Podman**: `podman compose` (`compose.yaml`: `frappe`, `mariadb`, `redis-cache`, `redis-queue`, plus named volumes).

Documentation:
- `README.md`: the tutorial. Chapter 1 picks a hosting solution. Chapter 2 holds the shared roles and pins. Chapter 3 (VirtualBox) has the step-by-step procedure in 3.3, which mirrors the roles command for command. Chapter 4 (Podman) covers the compose build and storage, and 4.3 lists its differences.
- `docs/ops.md`: operating it (lifecycle, storage, backup, restore, timer, upgrades).
- `docs/developer.md`: the rules for changing it, and the gate matrix.
- `docs/troubleshooting.md`, `docs/todos.md`.

Docs must change in the same commit as the code they describe.

## Commands

This host has no VirtualBox. Verify with podman: `tests/gate.sh` is the single gate.

```bash
tests/gate.sh --quick     # static checks + app unit tests in the running test container (~1 min)
tests/gate.sh             # fresh build in tests/container (systemd stand-in for the VM) + re-run must be changed=0
tests/gate.sh --compose   # isolated compose project "frappe-gate" (ports 18080/19000): build, verify role,
                          # data + uploaded file survive container recreation, backup→restore round trip
```

Which gate to run:
- app or docs: `--quick`;
- `ansible/`, bootstrap, `Vagrantfile`, `tests/container/`: the full gate **and** `--compose`;
- `compose*`, `scripts/backup.sh`, `scripts/restore.sh`, `ops/`: `--compose`.

Static checks are `ansible-lint` (at the `production` profile, set in `ansible/.ansible-lint`), `vagrant validate --ignore-provider` and `podman compose config`.

Bench commands. VirtualBox and the test container use user `vagrant`, Podman uses user `frappe`; both run from `~/frappe-bench`:

```bash
podman exec -u vagrant -w /home/vagrant/frappe-bench -e PATH=/home/vagrant/.local/bin:/usr/local/bin:/usr/bin:/bin -e LANG=C.UTF-8 frappe-dev-test bench …
podman compose exec -u frappe frappe bench …
bench --site hrcost.localhost run-tests --app hr_cost
bench --site hrcost.localhost run-tests --module hr_cost.hr_cost.doctype.work_record.test_work_record --test <method>
bench --site hrcost.localhost migrate
```

`migrate`, `install-app` and `run-tests` need the bench's redis: in VirtualBox that's the `frappe-bench` systemd service, in Podman the compose redis services. Python changes need a bench restart, because workers don't reload.

Backups: `scripts/backup.sh [--target compose|vm] [--dry-run]` and `scripts/restore.sh --from backups/<ts> (--yes|--dry-run)`. **Never enable the backup timer** (`systemctl --user enable …`). `scripts/install-backup-timer.sh` renders and verifies it as a dry run, and that is as far as it goes.

## Provisioning architecture

- **Pins live in one place each.** The box is in the `Vagrantfile`. ansible-core is in `ansible/requirements.txt`, which `scripts/bootstrap-ansible.sh` reads for the VM, the test container and the image. The MariaDB and redis image tags are in `compose.yaml`. Everything else is in `ansible/group_vars/all.yml`, including **`frappe_commit`**. Frappe develop requires Python `>=3.14,<3.15` and Node `>=24`.
- **Role order** (`site.yml`): base → mariadb → nodejs → bench → site → bench_service → hr_cost_app → verify. It's load-bearing: the bench's redis must be running before the app role, and the app enters `sites/apps.txt` only after it is pip-installed. The single `Restart frappe-bench` handler lives in `bench_service`.
- **`deploy_target`** (`vm` | `container`, set by `ansible/vars/container.yml`) is the only switch between the paths.
  - `container` skips the `mariadb` and `bench_service` roles and the systemd and sysctl tasks.
  - It sets `--db-host mariadb` and login scope `%`.
  - It merges the redis service URLs into `common_site_config.json` and writes a Procfile without redis.
  - The image build (`compose/Containerfile`) runs tags `base,nodejs,bench`. `compose/entrypoint.sh` runs `site,app` on every start, then `exec runuser -u frappe -- bench start`.
- **Pinned Frappe commit**: `bench init` can only clone branches, so the `bench` role fetches `frappe_commit` into `~/src/frappe` as a local `develop` branch and runs `bench init --frappe-path`. A failed init is cleaned up (block/rescue).
- **App install**: the bench's `apps/hr_cost` is a **symlink** to the repo (`/vagrant/...` or `/workspace/...`), plus an editable `uv pip install` and a line in `apps.txt`. `bench get-app` isn't used, because it needs a git repo root. Desk edits in developer mode write JSON straight into this repo.
- **VM must-haves**:
  - `FRAPPE_BIND_ADDR=0.0.0.0`, because NAT and port publishing can't reach 127.0.0.1;
  - host port 9000 stays 9000, because the browser connects to `socketio_port`;
  - `ansible.config_file` is set explicitly, because Ansible ignores `ansible.cfg` in the world-writable vboxsf cwd;
  - `ExecStartPre` waits for the shared folder.
- **Compose storage**:
  - `db-data`, `site-data` (only `sites/hrcost.localhost`: config, uploads, the encryption key) and `queue-data` are the volumes. `db-data` and `site-data` must be kept or wiped together.
  - Code and built assets live in the image, so all of `sites/` is **not** a volume.
  - Because the site dir is a mount point, `new-site` needs `--force`. That's safe only because the task is gated on a missing `site_config.json`.
  - `userns_mode: keep-id` plus `user: root` makes repo writes belong to the host user.
  - podman-compose doesn't recreate containers on image change: use `down && up -d --build`.
- **Idempotency**: a second run must report `changed=0`. Registered variables carry their role's prefix (ansible-lint).

## hr_cost app

- Frappe 17 app layout: a flit `pyproject.toml` and the `.frappe` module sentinel. The module "HR Cost" is at `apps/hr_cost/hr_cost/hr_cost/`.
- DocType and Report JSON are **generated by Frappe** in developer mode. Don't hand-author them. Keep `# begin/end: auto-generated types` and `_DOCTYPE_NAME` untouched in controllers.
- `work_record.py` holds the rules:
  - `hourly_rate` is the rate **valid on the record's date**, from the Employee's Hourly Rate History (child DocType `Employee Hourly Rate`; an empty `Valid From` is the base rate), looked up by `get_hourly_rate` in `employee.py`;
  - editing the history re-costs that employee's records (`recalculate_work_records`); Employee's own `hourly_rate` is a read-only mirror of the latest rate after creation;
  - no future dates; the Employee row is locked (`for_update`) during the 24 h check;
  - the `(employee, date)` index comes from `on_doctype_update` in `work_record.py` (Frappe JSON only declares single-column indexes);
  - `cost = hours × rate`;
  - at most 24 h per employee per date.
- The reports (`report/daily_hr_cost/`, `report/monthly_hr_cost/`) are `frappe.qb` GROUP BYs over the **stored** `cost` (by date; by employee and month). `frappe.qb` bypasses user permissions, which is acceptable only while the reports are System-Manager-only.
- Tests use `IntegrationTestCase`, roll back in `tearDown`, and use 2001 dates to avoid the demo data. Helpers are in `hr_cost/tests/utils.py`.
- `demo.create_demo_data` must stay idempotent. Provisioning's `changed_when` matches its `{"created": 0}` output.
- Frappe 17 serves the desk at `/desk/...`; `/app/...` redirects there.

## Skills

`.claude/skills/`:
- `code-review`
- `security-audit`
- `check-updates` (report-only)
- `docs-engineering`
- `commit-and-push` (Conventional Commits, straight to `main`, after the right gate)
- `release-engineering`
