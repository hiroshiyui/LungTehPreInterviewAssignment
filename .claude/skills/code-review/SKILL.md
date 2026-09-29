---
name: code-review
description: Perform a project-wide full-scope code review of this Frappe onboarding project — both provisioning paths (Vagrant/VirtualBox and podman compose, sharing one Ansible playbook: reproducibility, idempotency, role ordering, deploy_target switching, storage/backups), the hr_cost Frappe app (correctness, business rules, tests), documentation/tutorial accuracy, and code smells — then report findings by severity and fix the critical ones.
---

When performing a code review, do a **full project-wide sweep**, not just the recent changes.
Read widely across the codebase and apply every check below.

This project is a **long-term beginners' onboarding tutorial**. A newcomer runs `vagrant up` (VirtualBox) or
`podman compose up -d --build` (Podman), follows `README.md` and `docs/`, and reads the code
to learn from it. So there are two kinds of defect:
things that break (the build, the app, the tests), and things that **mislead a learner**
(docs that no longer match the code, clever-but-opaque code, silent magic). Treat both as real.

---

## Step 1 — Orient

- Read `CLAUDE.md` (commands, provisioning architecture, app conventions), `README.md`
  (the tutorial: one chapter per hosting solution; section 3.3 mirrors the Ansible roles
  one-to-one, and 4.3 covers the Podman differences), and `docs/developer.md` (the "deliberately odd" table).
- Skim `Vagrantfile`, `compose.yaml`, `compose/`, `ansible/site.yml`,
  `ansible/group_vars/all.yml`, `ansible/vars/container.yml`, each role under
  `ansible/roles/`, `scripts/`, and the app under `apps/hr_cost/hr_cost/hr_cost/`.
- Priorities, in order: **anything that makes `vagrant up` or `podman compose up` fail, or
  build a different environment** → data safety (volumes, backup/restore) → app
  correctness → tests → docs.

---

## Step 2 — Provisioning: reproducibility

The core promise is: *same inputs → same VM*. Anything that silently floats breaks it.

- **Every version that affects the result is pinned** and lives in one place: the box in
  the `Vagrantfile`, ansible-core in `ansible/requirements.txt`, the MariaDB and redis
  image tags in `compose.yaml`, and everything else in `ansible/group_vars/all.yml` (uv,
  Python, Node major, yarn, frappe-bench, **`frappe_commit`**). Flag hardcoded versions inside roles, and `latest` / unpinned
  `pip install` / `npm install -g <pkg>` without a version.
- Downloads are integrity-checked (the uv tarball uses a `sha256:` checksum URL). A new
  `get_url` without a `checksum:` is a finding.
- `scripts/bootstrap-ansible.sh` reads the pin from `ansible/requirements.txt` (the
  `ansible-core==X` line) for the VM, the test container and the compose image alike.
- Frappe `develop` constraints hold: Python `>=3.14,<3.15` and Node `>=24`. Check them
  against the pinned commit's `pyproject.toml` / `package.json` whenever `frappe_commit` moves.

## Step 3 — Provisioning: idempotency and ordering

- **A second run must report `changed=0`.** Every `command`/`shell` task needs
  `creates:`, a `when:` guarded by a pre-check, or an honest `changed_when:`. A bare
  `changed_when: false` on a task that really mutates state is a lie. The accepted
  exceptions carry a comment (`set-config`, `migrate`: "idempotent").
- **Role order in `site.yml` is load-bearing**: `bench` → `site` → `bench_service` →
  `hr_cost_app` → `verify`. `bench migrate` / `install-app` / `run-tests` need the bench's
  own redis, which runs under `frappe-bench.service`. The app may join `sites/apps.txt` only
  *after* it is pip-installed, or the running service crashes on import.
- Handlers are play-global. The single `Restart frappe-bench` handler lives in
  `bench_service`. A duplicate handler with the same name in another role is a finding.
- Bench commands run as `{{ frappe_user }}` with `environment: "{{ bench_env }}"`. A bench or
  uv command run as root, or without `bench_env`, is a finding: it leaves root-owned files in
  the bench.
- VM-specific must-haves stay intact:
  - `FRAPPE_BIND_ADDR=0.0.0.0` in the unit, because NAT can't reach 127.0.0.1.
  - The `ExecStartPre` wait for the shared folder.
  - Host port 9000 forwarded as 9000, for Socket.IO.
  - `ansible.config_file` set explicitly, because the vboxsf share is world-writable.
- `ansible-lint` passes at the `production` profile (`ansible/.ansible-lint`). Registered
  variables carry their role's prefix.

## Step 3b — The Podman (compose) solution

- **One playbook, two targets.** Container-specific behaviour sits behind
  `deploy_target == 'container'` (set by `ansible/vars/container.yml`), never in a forked
  role. Flag duplicated logic between `compose/entrypoint.sh` and the roles: the entrypoint
  should only wait for the DB, run `--tags site,app`, and exec `bench start`.
- **Build/run split**: the image build runs tags `base,nodejs,bench`, and the entrypoint
  runs `site,app`. A new role must fall into one group, or be skipped for containers.
  Anything needing MariaDB or redis must not run at image-build time.
- **Storage invariants**:
  - Only `sites/<site>` is a volume (`site-data`), alongside `db-data` and `queue-data`.
  - Persisting all of `sites/` is a finding: stale built assets would survive image
    rebuilds.
  - The `site-data` mount path in `compose.yaml` must match `SITE_NAME`.
  - `new-site --force` is safe only because the task is gated on a missing
    `site_config.json`.
- **Re-start safety**: every start re-runs `site,app`, so they must be idempotent on an
  existing site, including the default-site JSON merge.
- **Services**: redis URLs in `common_site_config.json` point at the service names; the
  Procfile template has no redis lines; the DB user login scope is `%`; `userns_mode:
  keep-id` plus `user: root`, dropping to `frappe` via `runuser`.
- **Ports** bind to `127.0.0.1`. The realtime host port defaults to 9000; overriding it is
  for tests only.

## Step 3c — Backups and the timer

- `scripts/backup.sh` and `restore.sh` work for both targets and support `--dry-run`.
  Restore refuses to run without `--yes`. Backup retention never deletes anything outside
  `backups/20*`.
- The backup lands **outside** what it protects: `--backup-path` goes through the bind
  mount or shared folder into `./backups` on the host.
- The systemd timer is **never enabled by any script** (`scripts/install-backup-timer.sh`
  only renders, verifies and optionally installs). Any `systemctl enable` added to a
  script is a Critical finding: it contradicts an explicit project decision.

## Step 4 — The hr_cost app: correctness

- **Work Record business rules** (`work_record.py`):
  - Pay follows the employment contract: each Pay History row is Hourly (`hourly_rate`) or
    Monthly (`monthly_salary`). `hourly_rate` on a record is the rate **valid on its date**,
    never today's; 0 under monthly pay (the salary covers the hours). History edits re-cost
    affected records; an edit that would leave a record without pay terms is refused.
  - No future dates, and within the employment (Date of Joining to Relieving Date); the
    Employee row is locked (`for_update`) during the 24 h check.
  - `cost = hours_worked × hourly_rate`, rounded with `self.precision("cost")`.
  - `hours_worked > 0`, and at most 24 h per employee per date, summed across *other*
    records (`name != self.name`, so an edit doesn't count itself).
- **Reports** (`report/daily_hr_cost/`, `report/monthly_hr_cost/`) sum the **stored** `cost`. They must
  never recompute from a current rate, because that would rewrite history. They add monthly
  salaries at ÷ 30 per calendar day (`get_salary_costs`), within the employment and never
  beyond today, read through `report/salaries.py` (pay access and User Permissions).
  - Each validates its filters (both dates required, from ≤ to).
  - Each returns `columns, data, None, chart, summary`, and `chart` is `None` when there's no
    data.
- **Generated code stays generated.** DocType and Report JSON come from Frappe's developer
  mode. The `# begin/end: auto-generated types` blocks and `_DOCTYPE_NAME` must be untouched.
  Hand-edited JSON that drifts from Frappe's format (missing `modified` bump, keys out of
  order) is a finding: make the change through the Desk or the API instead.
- Client script (`work_record.js`) only *previews* the cost; the server is authoritative.
  Flag any logic that exists only client-side.
- Queries use `frappe.qb` or parameterized `frappe.db` calls. Report queries use
  `frappe.qb.get_query(..., ignore_permissions=False)` so roles, User Permissions and
  permlevels apply; a report built on plain `frappe.qb.from_()` leaks pay to anyone who
  can open it.
- Pay (rates, rate history, cost) is permlevel 1, readable only by HR Manager. Anything
  new that shows a rate or cost (a field, an endpoint, a report column) respects that,
  and `tests/test_permissions.py` covers it.
- `demo.py` stays idempotent: a second call creates nothing and returns `{"created": 0}`.
  The Ansible `changed_when` depends on that exact output.

## Step 5 — Tests

- Every business rule and every report behaviour has an `IntegrationTestCase` test, and so
  do the **negative paths**: zero hours, over 24 h, a rate change not rewriting history, an
  invalid date range, an empty range.
- Tests roll back in `tearDown`, and use far-past dates (2001) so they can't collide with the
  demo data. Shared helpers live in `hr_cost/tests/utils.py`.
- The `verify` role runs the full app suite during provisioning. A test that only passes on
  a warm bench, or depends on the current date, is a finding.

## Step 6 — Documentation and tutorial accuracy

- **`README.md` section 3.3 matches the roles, command for command** (4.3 for Podman). If a
  role changed and the manual equivalent didn't, a beginner following the manual path will
  fail.
- `docs/ops.md` (lifecycle, storage table, backup, restore, timer),
  `docs/troubleshooting.md`, `docs/developer.md` (gate matrix, odd-but-deliberate table)
  and `docs/todos.md` match the code. A finished TODO that's still listed is a finding.
- The version tables (chapter 2, 3.1, 4.1), the URLs (Frappe 17 uses `/desk/...`), the credentials, and
  the troubleshooting table all match the current code.
- `CLAUDE.md` and `apps/hr_cost/README.md` agree with the code.
- Comments explain *why* (NAT binding, world-writable cwd, rate by work date), not *what*.
  A non-obvious line with no *why* comment is a Minor finding. In a tutorial it's a missed
  lesson.

## Step 7 — Code smells

- Duplication between roles that should be a variable; magic strings that duplicate a
  `group_vars` value (site name, paths, ports).
- Stale code: unused registered variables, dead tasks, leftover debug output.
- Over-clever code a beginner can't follow — dense Jinja filter chains, one-liner shell
  pipelines inside `shell:` — when a plainer form exists.

---

## Reporting

Group all findings by severity:

| Severity | Criteria |
|----------|----------|
| **Critical** | `vagrant up` / `podman compose up` fails or builds a different environment; data loss (a volume layout that drops data on recreate, a broken restore, retention deleting the wrong files); data-corrupting app logic; the backup timer enabled by a script; a secret committed |
| **Major** | Idempotency broken (`changed>0` on re-run, or a changing container restart); wrong role order or build/run split; a missing test for a business rule; README/docs steps that no longer work; a business rule enforced only client-side |
| **Minor** | Style, unclear naming, a missing *why* comment, lint drift, stale docs that don't block anyone |

For each finding, cite **file:line**, describe the issue and who it affects (the build, the
app user, or the beginner reading along), and give a **concrete fix**. If a category was
checked and is clean, say so.

---

## Fixing

Fix every **Critical** and **Major** finding directly, then run the gate:

```bash
tests/gate.sh --quick     # app-only changes: static checks + unit tests
tests/gate.sh             # ansible/, bootstrap, Vagrantfile, tests/container: fresh build + idempotency
tests/gate.sh --compose   # compose.yaml, compose/, backup/restore scripts, and ALSO for ansible/ changes
```

The matrix is in `docs/developer.md` ("The gate").

The review isn't complete until the right gate passes. When you find a bug class once, **sweep
the whole project for other instances** before finishing.
