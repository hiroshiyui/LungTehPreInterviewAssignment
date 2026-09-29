# Developer guide

How the project is put together, and how to change it safely: the app, the
provisioning, the tests, and the gate every change must pass. To just run the
environment, see [ops.md](ops.md).

---

## 1. Mental model

```
             ansible/  (one playbook, one set of pins)
            /                                   \
  VirtualBox (Vagrant) VM               Podman (compose)
  bootstrap → ansible_local             Containerfile: base, nodejs, bench roles
  all roles, deploy_target=vm           entrypoint:    site, app roles → bench start
            \                                   /
             apps/hr_cost  (this repo; symlinked into the bench)
```

- **One source of truth for versions.** `ansible/group_vars/all.yml` holds
  them, plus `ansible/requirements.txt` for ansible-core. Nothing else
  hardcodes a version, except the box in the `Vagrantfile` and the MariaDB and
  redis image tags in `compose.yaml`.
- **One source of truth for the app.** `apps/hr_cost` in this repo. The bench
  links to it, so the bench never holds a copy.
- **`deploy_target`** (`vm` | `container`) is the only switch between the paths.
  Keep container-specific logic behind it, and keep the roles themselves shared.

## 2. Working on the app

Get a shell where `bench` works:

```bash
vagrant ssh                                   # VirtualBox (user vagrant)
podman compose exec -u frappe frappe bash     # Podman (user frappe)
cd ~/frappe-bench
```

| Task | Command (inside the bench) |
| --- | --- |
| Run all app tests | `bench --site hrcost.localhost run-tests --app hr_cost` |
| One test module | `bench --site hrcost.localhost run-tests --module hr_cost.hr_cost.doctype.work_record.test_work_record` |
| One test | add `--test test_cost_is_hours_times_rate` |
| Python console with frappe loaded | `bench --site hrcost.localhost console` |
| Apply DocType/Report JSON changes | `bench --site hrcost.localhost migrate` |
| Load demo data (idempotent) | `bench --site hrcost.localhost execute hr_cost.demo.create_demo_data` |

Edit files under `apps/hr_cost` **on the host**. How changes are picked up
depends on the hosting solution:

- **Podman**: the bind mount shares the host's file-change notifications, so
  the web server auto-reloads Python and the asset watcher sees JS changes.
- **VirtualBox**: the shared folder (vboxsf) does **not** pass host-side
  file-change notifications into the VM, so neither the web server nor the
  watcher notices an edit made on the host. After a change, restart the bench
  (`vagrant ssh -c 'sudo systemctl restart frappe-bench'`). Alternatively, edit
  the same files from inside the VM (`vagrant ssh`, under `/vagrant`), where
  the notifications do fire.

Either way, background workers never reload by themselves: restart the bench
after Python changes (`sudo systemctl restart frappe-bench` in the VM,
`podman compose restart frappe` in Podman). If a DocType or report change
still doesn't show, run `bench --site hrcost.localhost clear-cache` and
reload the page.

### Rules for the app code

- **Create DocTypes and Reports through Frappe** (the Desk UI in developer
  mode, or `frappe.get_doc({"doctype": "DocType", …}).insert()`), never by
  hand-writing JSON. Frappe exports the JSON into the repo. The same goes for
  changing fields.
- The reverse holds too: in developer mode, **deleting** a standard DocType or
  Report (Desk or `frappe.delete_doc`) deletes its folder from the repo, code
  and tests included. Commit before you experiment, and to re-sync one from its
  JSON, delete only the database row and run `bench migrate`.
- In controllers, keep the `# begin/end: auto-generated types` block and
  `_DOCTYPE_NAME` untouched. Frappe rewrites them.
- **Pay is permlevel 1** (rates, the rate history, costs), readable only by HR
  Manager; HR User enters work records without seeing it. A report or endpoint
  that returns pay must honour that: build report queries with
  `frappe.qb.get_query(..., ignore_permissions=False)`, and check the permlevel
  in whitelisted methods (`get_hourly_rate_on`). Plain `frappe.qb.from_()` and
  `frappe.get_all` skip every permission check. When you add a permission row,
  set every right explicitly: DocPerm defaults most of them to 1.
- **Plots read the reports.** A chart or number card for the workspace is a
  Report-type Dashboard Chart or Number Card on one of the two reports, never
  a Document Type one on Work Record: that way it inherits the reports'
  permission checks. To check a chart by eye, open it in a browser; the
  unit tests cover its data.
- **README screenshots** (`docs/images/`) are taken at 1400 px wide as the
  demo users, on the demo data. Retake them when the UI they show changes.
- Business rules live on the **server** (`validate()`). The client script
  (`work_record.js`) only previews values.
- Pay follows the employment contract, **hourly or monthly**. A Work
  Record's rate is the one **valid on its date**, from the employee's Pay
  History (`get_hourly_rate` in `employee.py`), never the current rate; under
  monthly pay it's 0. Salaries accrue at ÷ 30 per calendar day
  (`get_salary_costs`) and the reports add them. The reports sum the **stored** `cost`; history edits re-cost records
  through `recalculate_work_records`.
- Schema changes that affect existing data ship with a patch in
  `hr_cost/patches/` (listed in `patches.txt`), plus a test for it.
- Tests use `IntegrationTestCase`, roll back in `tearDown`, and use dates in 2001
  so they never collide with the demo data. Shared helpers are in
  `hr_cost/tests/utils.py`.
- Every new business rule gets a test, including the negative path (the
  input it must reject).

Where things are:

| Path | What |
| --- | --- |
| `apps/hr_cost/hr_cost/hr_cost/doctype/employee/` | Employee: rate history rules, rate lookup by date, re-costing + tests |
| `apps/hr_cost/hr_cost/hr_cost/doctype/employee_hourly_rate/` | the Hourly Rate History rows (child DocType) |
| `apps/hr_cost/hr_cost/hr_cost/doctype/work_record/` | Work Record: rate by date, cost, no future dates, 24 h cap, indexes |
| `apps/hr_cost/hr_cost/hr_cost/report/daily_hr_cost/` | Daily HR Cost: the Script Report (py + js filters) + tests |
| `apps/hr_cost/hr_cost/hr_cost/report/monthly_hr_cost/` | Monthly HR Cost: employees × months, same layout |
| `apps/hr_cost/hr_cost/hr_cost/workspace/`, `dashboard_chart/`, `number_card/` | the HR Cost workspace and its charts and cards (all Report-based) |
| `apps/hr_cost/hr_cost/hr_cost/report/pdf.py`, `report_pdf.html` | the reports' "Download PDF" (server-rendered A4, wkhtmltopdf) |
| `apps/hr_cost/hr_cost/hr_cost/report/scope.py` | the reports' Employee and Nationality filters, as one permission-aware employee list |
| `apps/hr_cost/hr_cost/hr_cost/doctype/employee_other_name/` | names in other writing systems (child DocType) |
| `apps/hr_cost/hr_cost/hr_cost/report/salaries.py` | monthly salaries for both reports, with the pay-access and User Permission checks |
| `apps/hr_cost/hr_cost/setup.py` | answers Frappe's setup wizard (run by provisioning, before the demo users) |
| `apps/hr_cost/hr_cost/demo.py` | demo data (run by provisioning): hourly staff with a raise, a salaried employee, one user per HR role |
| `apps/hr_cost/hr_cost/patches/` | data migrations run by `bench migrate` |
| `apps/hr_cost/hr_cost/fixtures/role.json` | the HR Manager and HR User roles (`bench export-fixtures`) |
| `apps/hr_cost/hr_cost/tests/` | shared test helpers; demo, patch and permission tests |

## 3. Working on the provisioning

- Roles run in this order (`ansible/site.yml`): `base` → `mariadb` → `nodejs`
  → `bench` → `site` → `bench_service` → `hr_cost_app` → `verify`. **The order
  is load-bearing.** `bench migrate`, `install-app` and `run-tests` need the
  bench's redis, so the bench service (or the compose redis services) must be
  up before the app role runs. `hr_cost` may be added to `sites/apps.txt` only
  after it is pip-installed.
- **Idempotency**: a second run must report `changed=0`. Every
  `command`/`shell` task needs `creates:`, a pre-check with `when:`, or an
  honest `changed_when:`.
- Bench, uv and git commands run as `{{ frappe_user }}` with
  `environment: "{{ bench_env }}"`, never as root.
- `ansible-lint` must pass at the `production` profile (`ansible/.ansible-lint`).
  Registered variables take their role's name as a prefix (`bench_…`, `verify_…`).
- In Podman, the image build runs roles `base,nodejs,bench`, and the entrypoint
  runs `site,app`. A new role must be placed in one of those groups (by tag)
  or be skipped via `deploy_target`.
- **Pins.** Every input is pinned: image digests (`compose.yaml`, both
  Containerfiles), `group_vars` (including `frappe_commit` and the exact
  `nodejs_version`) and Frappe's Python packages
  (`roles/bench/files/python-constraints.txt`, which the `verify` role checks).
  After moving `frappe_commit`, regenerate the constraints:
  `tests/gate.sh && scripts/freeze-python-deps.sh && tests/gate.sh`. Ubuntu's apt
  packages deliberately follow the archive, so they get security updates.
- Changing anything under `ansible/` invalidates the image's `COPY ansible`
  layer, so the next `podman compose up --build` re-runs `bench init` (about
  6–10 minutes).

Things that look odd but are deliberate:

| What | Why |
| --- | --- |
| `FRAPPE_BIND_ADDR=0.0.0.0` (VM unit, image) | `bench serve` binds to 127.0.0.1 by default. NAT and container port publishing can't reach that. |
| host port 9000 is never remapped | the browser's Socket.IO client connects to `socketio_port` (9000) on the page's host |
| `ansible.config_file` in the Vagrantfile | Ansible ignores `ansible.cfg` in a world-writable directory (the vboxsf share) |
| the frappe commit is fetched into `~/src/frappe` and named `develop` | `bench init` can only clone branches; this pins an exact commit |
| `ExecStartPre` waits for the app directory | the VirtualBox shared folder is mounted after boot |
| `new-site --force` in Podman | the site directory is a volume mount point, so it always exists; the task still only runs while `site_config.json` is missing |
| `userns_mode: keep-id` + `user: root` in compose | files the container writes into the repo belong to you; the entrypoint then drops to `frappe` |

## 4. The gate

One command decides whether a change is ready to commit:

```bash
tests/gate.sh --quick     # ~1 min: static checks + app unit tests (needs the test container)
tests/gate.sh             # ~8 min: fresh build in the test container + idempotency re-run
tests/gate.sh --compose   # ~3 min on a warm image: compose build/start, verify role,
                          # persistence across container recreation, backup→restore round trip
```

| You changed | Run |
| --- | --- |
| only `apps/hr_cost/**` or docs | `--quick` |
| `ansible/**`, `scripts/bootstrap-ansible.sh`, `Vagrantfile`, `tests/container/**` | the full gate **and** `--compose` |
| `compose.yaml`, `compose/**`, `scripts/backup.sh`, `scripts/restore.sh` | `--compose` |

Static checks cover: shell syntax, the app's JSON, `vagrant validate`,
`podman compose config` and `ansible-lint`.

**The test container** (`tests/container/run.sh`) is a systemd Ubuntu 24.04
container with a `vagrant` user and the repo mounted at `/vagrant`. It's a
faithful stand-in for the VM that runs the same bootstrap and playbook. It
serves on http://127.0.0.1:18000. The compose gate uses its own project
(`frappe-gate`) and ports (18080 and 19000), and removes it afterwards, so it
never touches your `frappe-dev` stack.

Neither gate exercises real VirtualBox (vboxsf, NAT, the box). Before a
release, also run `vagrant destroy -f && vagrant up` on a host with VirtualBox.

## 5. Conventions

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/),
  explaining *why*. Scopes: `vagrant`, `compose`, `ansible` (or a role name),
  `app`, `report`, `ops`, `docs`, `tests`, `deps`, `frappe`.
- **Docs change with code.** When a role changes, update README section 3.3 (and 4.3 if the Podman solution differs).
  When a pin changes, update the version table. When you meet a new failure
  mode, add it to [troubleshooting.md](troubleshooting.md).
- Comments say *why*, not *what*. In a tutorial, an unexplained line is a
  missed lesson.

## 6. Claude Code skills

`.claude/skills/` contains project-specific workflows for Claude Code:

| Skill | Use it to |
| --- | --- |
| `code-review` | review the whole project: reproducibility, idempotency, app rules, tests, docs |
| `security-audit` | audit the supply chain, exposure, credentials, privileges, and app permissions |
| `check-updates` | report outdated pins (box, images, ansible-core, uv, bench, frappe commit) |
| `docs-engineering` | bring all docs back in line with the code, for beginners |
| `commit-and-push` | commit after the right gate |
| `release-engineering` | cut a tagged, tested tutorial snapshot |
