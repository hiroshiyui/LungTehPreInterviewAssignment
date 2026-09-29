---
name: security-audit
description: Perform a dedicated security audit of this Frappe onboarding project (Vagrant VM and podman compose paths) — supply-chain integrity (pins, checksums, signed repos, container images), network exposure, credentials and backup secrets, privilege use in Ansible/systemd/containers, and the hr_cost app's Frappe permissions, whitelisting and query safety — mapped to the OWASP Top 10, then report findings by severity and fix the critical ones.
---

This project builds a **development environment** for beginners: a VM (VirtualBox) or a
podman compose stack (Podman). It's not a production deployment, and
its fixed credentials (`admin` / `frappe`) are deliberate. The threats that matter are the
ones a learner inherits without noticing:

1. **Supply chain**: the build downloads a lot (box, apt repos, uv, Python, PyPI, npm,
   GitHub). A tampered or floating input compromises every VM built from this repo.
2. **Exposure**: a dev VM with known credentials must never be reachable from the network.
3. **Bad habits learned**: whatever the tutorial shows (running as root, `curl | sh`,
   world-open ports, unchecked SQL) gets copied into real projects.
4. **The app**: permission and query mistakes in `hr_cost` are the pattern learners reuse.

This skill covers security only. For correctness, tests and docs, use `code-review`.

---

## Step 1 — Orient and threat-model

- Read `CLAUDE.md`, `README.md` (chapters 2–4) and `docs/ops.md` (storage, backups,
  security notes). Then read `Vagrantfile`, `compose.yaml`, `compose/`, `scripts/`,
  `ops/systemd/`, `ansible/group_vars/all.yml`, `ansible/vars/container.yml`, every role,
  and `apps/hr_cost`.
- Enumerate every **network fetch** the build makes and every **listening port** the VM
  opens. Those two lists are the attack surface.

## Step 2 — Supply-chain integrity (A08, A06)

- **Pinned, not floating.** The box version, ansible-core, uv, Python minor, Node major, yarn,
  frappe-bench and `frappe_commit` are all pinned. A new unpinned fetch is a finding. So is a
  branch where a commit SHA belongs. `frappe_commit: ""` is allowed only as a documented
  opt-in.
- **Verified downloads.**
  - The uv tarball is `sha256`-checked, so any new `get_url` needs a `checksum:`.
  - Apt repos use deb822 with `signed_by` (NodeSource). Flag `trusted=yes`, `[allow-insecure]`
    and `apt-key`.
  - No `curl … | sh` / `bash` anywhere, not even in README examples.
  - The frappe source is fetched by exact commit SHA over HTTPS.
- **Box and image provenance.** `bento/` is the Chef Bento project's namespace. The
  container images are Docker Official Images, fully qualified (`docker.io/library/…`).
  Flag an unknown publisher, or an unqualified short name (podman may resolve it through
  another registry). Images are pinned by tag, not digest; that's a known gap tracked in
  `docs/todos.md`.
- **Lockfiles and dependencies.** Frappe's Python and JS dependencies resolve during
  `bench init` from the pinned commit's manifests. `pyproject.toml` has `~=` ranges, so
  builds are **not bit-for-bit reproducible**; note it rather than "fix" it. The app itself
  declares no third-party dependencies; flag any added without a pin.

## Step 3 — Network exposure (A05)

- Every `forwarded_port` in the `Vagrantfile` has `host_ip: "127.0.0.1"`. Flag any
  forward without it, and any `public_network` / `private_network`: known credentials plus a
  LAN-visible port is a real compromise.
- Inside the guest:
  - `FRAPPE_BIND_ADDR=0.0.0.0` is needed for NAT and is safe only *because of* the
    loopback-bound host forwards. Keep the comment that says so.
  - MariaDB stays local: the user host login scope is `localhost` and there's no
    `bind-address = 0.0.0.0`.
  - The distro redis is disabled, and bench's redis binds to localhost.
- `tests/container/run.sh` publishes `127.0.0.1:18000` only.
- **compose.yaml**:
  - Every `ports:` entry is `127.0.0.1:…`.
  - `mariadb` and `redis-*` publish **no** ports; they're reachable only on the compose
    network.
  - The DB user login scope `%` is acceptable *only* because MariaDB isn't published.
    Publishing 3306 would turn that into a remote login.

## Step 4 — Credentials and secrets (A02, A07)

- `admin_password` and `mariadb_root_password` are **dev-only, documented, and localhost-only**.
  That is intended; they must not be reused for anything else, and the README must keep
  labelling them as dev-only.
- Password-bearing tasks use `no_log: true` (the MariaDB root tasks, the verify login). Flag
  any new task that echoes a password in `argv` without `no_log`.
- Nothing secret is committed: no `site_config.json`, `.vagrant/` (private keys),
  `encryption_key`, `*.pem`, or **`backups/`**. Each backup set's
  `*-site_config_backup.json` holds the site's `encryption_key` and DB password. Check
  `.gitignore` and `git ls-files`.
- Compose passwords come from `${DB_ROOT_PASSWORD:-frappe}` / `${ADMIN_PASSWORD:-admin}`
  in one place. The entrypoint passes them to Ansible as extra vars; flag any path that
  echoes them (they appear in `podman inspect` env, which is acceptable for a dev stack).
- The MariaDB root account keeps `unix_socket` auth for the OS root user
  (`IDENTIFIED VIA unix_socket OR mysql_native_password`). Flag a change to password-only
  root.

## Step 5 — Privilege (A01, A05)

- Bench, uv, git and yarn run as `{{ frappe_user }}` (`become_user`), never as root. Only
  package installs, `/usr/local/bin` and `/etc` changes, and systemd use root.
- `frappe-bench.service` runs with `User={{ frappe_user }}`. Hardening directives such as
  `NoNewPrivileges=`, `ProtectSystem=` or `PrivateTmp=` are *optional* for a dev VM. Suggest
  them as Minor and don't add them silently: they can break `bench start`'s child processes.
- `/etc/sudoers.d` is untouched by the playbook (the box's own `vagrant` sudo is expected).
- **Containers**:
  - The frappe container starts as root only to fix volume ownership and run Ansible, then
    `exec runuser -u frappe`. `bench start` must never run as root.
  - `userns_mode: keep-id` maps the container's uid 1000 to the host user. Flag
    `privileged: true`, added capabilities, or host-path mounts beyond the repo.
- **Backup timer**: user units only, never enabled by any script. The service runs
  `scripts/backup.sh` from the repo, so the repo's integrity matters; keep write access
  to it limited to the user.

## Step 6 — The hr_cost app (A01, A03, A04)

- **Permissions and pay confidentiality**: the roles are `HR Manager` (everything,
  including pay) and `HR User` (enters work records), shipped as fixtures
  (`hr_cost/fixtures/role.json`). Pay (`hourly_rate`, the rate history, `cost`) sits at
  **permlevel 1**, which only HR Manager can read; `System Manager` keeps permlevel 0
  only. Both reports' `roles` are `HR Manager` only. Findings:
  - a new DocType or report without explicit roles, or with `Guest` / `All`;
  - a pay field left at permlevel 0, or a permlevel 1 row for any role but HR Manager;
  - a DocPerm row with rights it wasn't meant to have. DocPerm defaults most rights
    to 1, so every right must be set explicitly (check the JSON, not just the intent).
- **Queries that return pay**: the reports use `frappe.qb.get_query(...,
  ignore_permissions=False)`, which applies roles, User Permissions and permlevels.
  Salaries come through `report/salaries.py`, which refuses users without permlevel 1
  read on Employee and lists employees with `frappe.get_list` (User Permissions).
  Plain `frappe.qb.from_()` and `frappe.get_all` **bypass all three**: they're fine
  inside a controller (for example, costing a record), but a finding wherever results
  reach a user who may not see pay.
- **Injection**: all SQL goes through `frappe.qb` or parameterized `frappe.db` calls, never
  f-strings, `%` formatting or `frappe.db.sql` with interpolated user input. Filter values
  are normalized (`getdate`) before use.
- **Whitelisting**: any `@frappe.whitelist()` method checks permissions itself
  (`frappe.has_permission` / `doc.check_permission`), **and the permlevel of what it
  returns**: `get_hourly_rate_on` returns a rate, so it also requires permlevel 1 read on
  Employee. `allow_guest=True` needs a written
  justification. `demo.create_demo_data` is **not** whitelisted: it runs only via
  `bench execute` and must stay that way.
- **Server-side authority**: cost and hour limits are enforced in `validate()`. The
  client script is a convenience only.
- **Output encoding**: the report returns plain data and Frappe's datatable escapes it. Flag
  any HTML built from user data (`frappe.format` of raw HTML, custom formatters that inject
  markup).

## Step 7 — Dependency advisories (A06)

```bash
# inside the VM, the test container, or `podman compose exec -u frappe frappe bash`,
# as the bench user, from ~/frappe-bench
uv pip list --outdated --python env/bin/python      # outdated Python packages in the bench venv
uvx pip-audit --path env/lib/python3.14/site-packages   # PyPI advisories (OSV)
(cd apps/frappe && yarn audit --groups dependencies)    # npm advisories for frappe's JS
```

Triage each advisory for reachability in a *local dev VM* (most server-side web advisories
need exposure, which Step 3 rules out). Most fixes arrive by moving `frappe_commit`: see the
`check-updates` skill.

## Step 8 — OWASP Top 10 cross-check

| Category | Where |
|----------|-------|
| A01 Broken Access Control | 5, 6 |
| A02 Cryptographic Failures | 4 |
| A03 Injection | 6 |
| A04 Insecure Design | 3, 6 |
| A05 Security Misconfiguration | 3, 5 |
| A06 Vulnerable & Outdated Components | 2, 7 |
| A07 Identification & Auth Failures | 4 |
| A08 Software & Data Integrity Failures | 2 |
| A09 Logging & Monitoring Failures | 4 (`no_log`) — otherwise n/a for a dev VM |
| A10 SSRF | n/a: the app makes no server-side fetches of user-supplied URLs |

---

## Reporting

| Severity | Criteria |
|----------|----------|
| **Critical** | A VM or container port reachable beyond localhost (including a published MariaDB/redis); an unverified download; a committed secret, private key or backup set; an app endpoint open to Guest; SQL built from user input |
| **Major** | An unpinned input; a password echoed in logs; a bench command run as root; a report readable by roles that the `qb` query doesn't permission-check; a whitelisted method without a permission check |
| **Minor** | Optional hardening (systemd sandboxing), defense-in-depth, doc wording that could teach a bad habit |

For each finding: **file:line**, the vulnerability, a concrete **attack scenario** (who, from
where), and a **concrete fix**. Say which categories were checked and clean. Silence is not a
clean bill of health.

## Fixing

Fix every **Critical** and **Major** finding directly. Add a regression test for app-side
fixes. Then run the gate: `tests/gate.sh` and `tests/gate.sh --compose` for provisioning
changes, `tests/gate.sh --compose` for compose/backup changes, and `tests/gate.sh --quick`
for app-only ones. When a gap is found once, **sweep for the same class** everywhere before
finishing.
