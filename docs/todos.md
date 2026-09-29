# TODOs

Known gaps and planned work, most important first. When an item is done,
remove it here and mention it in the commit. When you decide against one,
move it to "Decided against" with the reason.

## Verification

- [ ] **Run the VirtualBox solution on real VirtualBox.** The playbook has been verified in the
  systemd test container (`tests/gate.sh`), but not yet in a VirtualBox VM:
  vboxsf permissions, NAT port forwarding, `ansible_local` and the bento box
  itself are untested. Run `vagrant destroy -f && vagrant up` on a host with
  VirtualBox 7.1+, then record the result.
- [ ] **CI**: run `tests/gate.sh --compose` and `tests/gate.sh` on every push
  once the repository has a remote (a GitHub Actions runner with podman).
- [ ] Check the desk UI after every `frappe_commit` move (forms, report page).
  The gates only cover the API and unit tests. Consider a browser smoke test
  (Playwright) for the report page.

## Reproducibility

- [ ] Pin the container base images by **digest** (`ubuntu:24.04`,
  `mariadb:10.11`, `redis:7.2-alpine`), not only by tag.
- [ ] Frappe's own Python and JS dependencies resolve from the pinned commit's
  `~=` / `^` ranges at `bench init` time, so two builds weeks apart can differ.
  Consider capturing a lock (`uv pip freeze`, `yarn.lock`) at build time.
- [ ] The Node.js patch version floats within `nodejs_major` (NodeSource).
  Pin the exact apt version if that ever bites.

## Operations

- [ ] Off-host backup copies: `scripts/backup.sh` writes to `./backups` on the
  same machine. Document or add an optional sync step (rsync or rclone).
- [ ] Backup encryption at rest: the sets contain the site's `encryption_key`
  (`bench backup --backup-encryption-key`).
- [ ] Health checks for the `frappe` compose service (`/api/method/ping`), so
  `podman compose ps` shows "healthy".

## App (`hr_cost`)

From the app review of 2026-09-29. Work through the steps in order; each
item ships with its tests.

### Steps 1–3 — Correctness, "calculate monthly", and pay confidentiality

Done:
- step 1: rates by work date (Hourly Rate History), re-costing on
  corrections, no future dates, the Employee row lock, `date` and
  `(employee, date)` indexes, and the missing tests;
- step 2: the Monthly HR Cost report (employees × months), and "Show days
  without work" on Daily HR Cost;
- step 3: HR Manager and HR User roles, pay at permlevel 1, permission-aware
  reports (roles, User Permissions, permlevels), and tests for each role.

One gap remains:

- [ ] The row lock that serialises the 24 h check has no automated test: a
  deterministic test needs two concurrent database connections, which the
  Frappe test runner doesn't provide.

### Step 4 — Polish

Informative plots for HR. Each plot ships with a test of its data, and each is
visible only to roles that may see pay (build charts and cards on the
permission-aware report queries, or on Work Record, never on raw SQL):

- [ ] Monthly HR Cost: stack each month's bar by employee, so the chart shows
  who the cost goes to, not only the total.
- [ ] Daily HR Cost: cost as bars with hours worked as a line on the same
  axis (Frappe's `axis-mixed` chart), so an expensive day with few hours
  stands out.
- [ ] Cost share by employee for the selected range (a donut chart).
- [ ] Effective hourly rate (total cost ÷ total hours) per month as a line,
  which shows the effect of raises and of the staff mix.
- [ ] Month-over-month change: this month's cost next to last month's, with the
  difference in the report summary.
- [ ] Rate history on the Employee form: a step line of `Valid From` →
  `Hourly Rate` (pay data, so HR Manager only).
- [ ] An "HR Cost" workspace with Number Cards (cost and hours this month,
  change vs last month) and Dashboard Charts (the cost trend, cost by
  employee), linking to both reports.

Other polish:

- [ ] Daily report: drill down from a day to its Work Records.
- [ ] `employee_name` on Work Record is copied at save time and goes stale
  when an Employee is renamed: drop it (links already show the current name)
  or refresh it on Employee save.
- [ ] `allow_rename` and `index_web_pages_for_search` are on for both
  DocTypes; neither makes sense for them.
- [ ] Duplicate employee names are indistinguishable in link dropdowns.
- [ ] `allow_import` + quick entry for Work Record (bulk / fast logging).
- [ ] Employee "Connections" to its Work Records; a dock entry for the
  module (the workspace is covered by the plots above).
- [ ] `pyproject.toml` still mentions `frappe~=16.0.0`.
- [ ] Demo users (one HR Manager, one HR User) so learners can see the
  difference between the roles without creating users by hand.

## Docs

- [ ] Screenshots of the report and the forms in the README (with alt text).
- [ ] `CHANGELOG.md` and the first tagged release (`release-engineering` skill).

## Decided against

- *Using `bench get-app` to install hr_cost*: it requires the app to be a git
  repository root. A symlink plus an editable install keeps the repo as the
  single source of truth.
- *Persisting all of `sites/` in Podman*: stale built assets would survive image
  rebuilds. Only the site directory is a volume.
