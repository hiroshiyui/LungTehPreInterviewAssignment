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

## App

- [ ] A "Monthly HR Cost" view (group by month) next to the daily report. The
  assignment's "calculate monthly" is currently covered by the report's
  period summary.
- [ ] Workspace / sidebar entry for the HR Cost module (Frappe 17 dock) so
  Employees, Work Records and the report are one click away.
- [ ] Roles: a dedicated "HR Manager" role instead of System Manager only.
  This needs permission-aware report queries (see the `security-audit` skill).

## Docs

- [ ] Screenshots of the report and the forms in the README (with alt text).
- [ ] `CHANGELOG.md` and the first tagged release (`release-engineering` skill).

## Decided against

- *Using `bench get-app` to install hr_cost*: it requires the app to be a git
  repository root. A symlink plus an editable install keeps the repo as the
  single source of truth.
- *Persisting all of `sites/` in Podman*: stale built assets would survive image
  rebuilds. Only the site directory is a volume.
