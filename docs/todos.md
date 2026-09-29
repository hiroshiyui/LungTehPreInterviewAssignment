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

### Steps 1–4, and pay per contract — done

Done:
- step 1: rates by work date (Hourly Rate History), re-costing on
  corrections, no future dates, the Employee row lock, `date` and
  `(employee, date)` indexes, and the missing tests;
- step 2: the Monthly HR Cost report (employees × months), and "Show days
  without work" on Daily HR Cost;
- step 3: HR Manager and HR User roles, pay at permlevel 1, permission-aware
  reports (roles, User Permissions, permlevels), and tests for each role;
- step 4, plots: a "Chart" picker on both reports (cost by employee, cost
  share, effective hourly rate; daily cost, hours, headcount), month-over-month
  change in the monthly summary, the rate history chart on Employee, and the
  HR Cost workspace (number cards and charts, all Report-based);
- step 4, polish: drill-down from a day to its Work Records, employee names
  kept current on Work Records, a warning for namesakes, import and quick
  entry for Work Records, Employee Connections, demo users per HR role,
  renaming and web indexing off, and README screenshots;
- pay per the employment contract (Taiwan's labour law): hourly or monthly
  pay terms in a dated Pay History, employment dates, salaries at ÷ 30 per
  calendar day in both reports, and provisioning that answers Frappe's setup
  wizard (country, time zone, currency);
- a "Download PDF" button on both reports (A4, wkhtmltopdf, Noto fonts for
  names in any script);
- staff from many countries: nationality (a report filter), names in other
  writing systems, work permit expiry reminders, per-user desk language.

Remaining:

- [ ] **Overtime for monthly-paid staff** (Labor Standards Act art. 24):
  hours beyond 8 a day at (salary ÷ 240) × 1.34 for the first 2 h and × 1.67
  for the next 2 h; rest days and public holidays have their own rates. For
  now a monthly-paid worker's Work Records cost nothing beyond the salary.
- [ ] Translate the app's own labels (field names, report titles, messages)
  into Traditional Chinese, Vietnamese, Thai and Indonesian; Frappe's own
  UI is already translated.
- [ ] Find employees by their names in other writing systems: link search
  only looks at Employee Name.
- [ ] A list or number card of work permits expiring in the next 30 days (for
  now: filter the Employee list by Work Permit Expiry).
- [ ] PDFs have the tables and figures but not the charts: wkhtmltopdf can't
  run the chart library. Render the chart as SVG on the server to include it.
- [ ] Hide the Pay History grid's Hourly Rate column for monthly rows (and
  Monthly Salary for hourly rows); it shows 0.00 there.

- [ ] The row lock that serialises the 24 h check has no automated test: a
  deterministic test needs two concurrent database connections, which the
  Frappe test runner doesn't provide.

## Docs

- [ ] `CHANGELOG.md` and the first tagged release (`release-engineering` skill).

## Decided against

- *A dock entry for the HR Cost module (for now)*: at the pinned Frappe commit
  the desk's Dock, Sidebar and Desktop Icon are being reworked (see
  `frappe/desk/RETIRING.md` there). Revisit when the pin moves. HR Users,
  who have no workspace because every card on it shows pay, reach Work
  Records from the sidebar.

- *One chart with cost bars and an hours line (`axis-mixed`)*: costs run in
  thousands and hours in tens, and Frappe's charts have one y axis, so the
  hours line lies flat. The Daily report offers separate charts instead.

- *Using `bench get-app` to install hr_cost*: it requires the app to be a git
  repository root. A symlink plus an editable install keeps the repo as the
  single source of truth.
- *Persisting all of `sites/` in Podman*: stale built assets would survive image
  rebuilds. Only the site directory is a volume.
