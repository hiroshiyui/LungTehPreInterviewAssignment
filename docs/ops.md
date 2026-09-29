# Operations

Running the environment day to day: starting and stopping it, where data
lives, backups and restore, scheduled backups, and upgrading pins. For
installation, see the [README](../README.md). For fixing problems, see
[troubleshooting.md](troubleshooting.md).

All commands run **on the host, from the repository root**, unless they say
otherwise.

---

## 1. Lifecycle

### VirtualBox (Vagrant)

| Task | Command |
| --- | --- |
| Create or start the VM | `vagrant up` |
| Re-apply provisioning (idempotent) | `vagrant provision` |
| Shell inside the VM | `vagrant ssh` |
| Stop / start | `vagrant halt`, then `vagrant up`; the bench starts automatically at boot |
| Service status and logs | `vagrant ssh -c 'systemctl status frappe-bench; journalctl -u frappe-bench -n 100'` |
| Restart the bench | `vagrant ssh -c 'sudo systemctl restart frappe-bench'` |
| Rebuild from nothing (**deletes all data**) | `vagrant destroy -f && vagrant up` |

### Podman (compose)

| Task | Command |
| --- | --- |
| Build and start | `podman compose up -d --build` |
| Status | `podman compose ps` |
| Logs | `podman compose logs -f frappe` (or `mariadb`, `redis-queue`, …) |
| Shell in the frappe container | `podman compose exec -u frappe frappe bash` |
| Stop (keeps containers) / start | `podman compose stop`, then `podman compose start` |
| Remove containers, **keep data** | `podman compose down` |
| Apply a rebuilt image | `podman compose down && podman compose up -d --build` |
| Wipe everything, **including data** | `podman compose down -v` |

`podman-compose` does **not** recreate a running container when its image
changes. After changing `compose/`, `ansible/` or `scripts/`, always use
`down`, then `up -d --build`. `down` keeps the named volumes.

On every start, the frappe container re-runs the `site` and `app` roles. The
first start creates the site. Later starts re-link the app and run `bench
migrate`, so a plain restart also applies DocType JSON changes from the repo.

## 2. Storage

### Where data lives

| Data | VirtualBox | Podman |
| --- | --- | --- |
| Database | MariaDB datadir inside the VM disk | volume `frappe-dev_db-data` → `/var/lib/mysql` |
| Site directory: `site_config.json` (DB credentials, **encryption key**), uploaded files (`public/files`, `private/files`), site logs | `~/frappe-bench/sites/hrcost.localhost` in the VM | volume `frappe-dev_site-data` → `sites/hrcost.localhost` |
| Background job queue | bench's local redis, in memory | volume `frappe-dev_queue-data` (redis-queue `/data`) |
| Cache | bench's local redis, in memory | redis-cache, in memory only (deliberately not persisted) |
| Code: frappe, the bench venv, built assets | VM disk | the `frappe` image (rebuilt, never persisted) |
| The hr_cost app | this repo (shared folder) | this repo (bind mount) |
| Backups | `./backups/` on the host | `./backups/` on the host |

Rules for Podman:

- **`db-data` and `site-data` belong together.** `site_config.json` holds the
  database name and password. Wiping only one of them leaves a site that can't
  open its database. Keep both, or wipe both (`podman compose down -v`).
- Only the *site* directory is a volume, not all of `sites/`. The bench-wide
  files (`apps.txt`, `common_site_config.json`, built `assets/`) come fresh from
  the image, so an image rebuild can never leave stale assets behind.
- Inspect a volume: `podman volume inspect frappe-dev_site-data`. Its files are
  under the `Mountpoint` shown there.

### Disk usage

```bash
podman system df -v | grep -E 'frappe-dev|VOLUME'   # Podman: image and volume sizes
du -sh backups/*                                     # backup sets
vagrant ssh -c 'df -h /'                             # VirtualBox: VM disk
```

## 3. Backups

A backup set is one directory, `backups/<timestamp>/`, containing:

| File | Contents |
| --- | --- |
| `*-database.sql.gz` | the full site database |
| `*-files.tar` | public uploaded files |
| `*-private-files.tar` | private uploaded files |
| `*-site_config_backup.json` | site config, including the **encryption key** |

```bash
scripts/backup.sh                  # Podman (default)
scripts/backup.sh --target vm      # VirtualBox
scripts/backup.sh --dry-run        # show what would run; changes nothing
scripts/backup.sh --keep 30        # retention: keep the newest 30 sets (default 14)
```

The script runs `bench backup --with-files --backup-path …`, which writes
**directly into `./backups/` on the host**: through the bind mount
(`/workspace`) in Podman, and through the shared folder (`/vagrant`) in VirtualBox.
The backup therefore lives outside the volumes or VM it protects. `backups/`
is git-ignored. Copy it somewhere else (another disk, cloud storage) if the
data matters.

> The site config backup contains the site's `encryption_key`. Treat backup
> sets as secrets.

## 4. Restore

**Destructive**: this replaces the site's database and files with the backup.

```bash
scripts/restore.sh --from backups/<timestamp> --dry-run   # show the commands
scripts/restore.sh --from backups/<timestamp> --yes       # Podman
scripts/restore.sh --from backups/<timestamp> --target vm --yes   # VirtualBox
```

The script runs `bench restore` with the database and both file archives, then
`bench migrate`. The set must be inside `./backups/`, because that is the only
host directory the container and the VM can see.

**Disaster recovery** (the volumes or the VM were lost, not just the data):

1. Start a fresh environment: `podman compose up -d --build`, or `vagrant up`.
2. Restore with `scripts/restore.sh … --yes`.
3. If documents contain encrypted fields (passwords, API keys), copy
   `encryption_key` from `*-site_config_backup.json` into the new site's
   `site_config.json`, then restart. Without it, those fields can't be
   decrypted.

`tests/gate.sh --compose` exercises the whole cycle on a throwaway stack: it
backs up, deletes a record, restores, and checks that the record and an
uploaded file are back.

## 5. Scheduled backups (systemd timer)

The repo ships a **systemd user timer** that would run `scripts/backup.sh`
daily at 03:00 (with up to 15 minutes of random delay, and catching up after
downtime):

- templates: `ops/systemd/frappe-backup.service.in` and `frappe-backup.timer.in`
- helper: `scripts/install-backup-timer.sh`

**The timer is never enabled automatically**, and nothing in this repo enables
it. Scheduling backups is a deliberate decision for whoever operates the
machine.

```bash
# 1. Dry run (the default): render the units with this repo's path, check them
#    with systemd-analyze, show the next trigger times, and dry-run the backup.
#    Installs nothing.
scripts/install-backup-timer.sh                 # Podman
scripts/install-backup-timer.sh --target vm     # VirtualBox

# 2. Optional: copy the units into ~/.config/systemd/user and reload systemd.
#    This still does NOT enable them.
scripts/install-backup-timer.sh --install

# 3. Only if you decide to schedule backups, enable the timer yourself:
systemctl --user enable --now frappe-backup.timer
systemctl --user list-timers frappe-backup.timer       # next run
journalctl --user -u frappe-backup.service             # results of past runs

# Undo:
systemctl --user disable --now frappe-backup.timer
rm ~/.config/systemd/user/frappe-backup.{service,timer} && systemctl --user daemon-reload
```

Notes:

- These are *user* units. By default they only run while you are logged in.
  To run them without a session, enable lingering: `loginctl enable-linger $USER`.
- The rendered units contain this repo's absolute path. Re-run the helper
  after moving the repository.

## 6. Upgrades

Every version is pinned (see the [README](../README.md#2-what-both-solutions-share)).
Moving a pin is a deliberate change:

1. **Back up first**: `scripts/backup.sh`.
2. Edit the pin in its single home: `ansible/group_vars/all.yml`,
   `ansible/requirements.txt`, `Vagrantfile` (box), or `compose.yaml` (the
   MariaDB and redis images).
3. Apply it:
   - VirtualBox: `vagrant provision`. A new `frappe_commit` does not re-run
     `bench init` on an existing bench; for that, `vagrant destroy -f && vagrant up`,
     then restore.
   - Podman: `podman compose down && podman compose up -d --build`. The image is
     rebuilt; the volumes keep the data, and `bench migrate` runs on start.
4. Run the gate (see [developer.md](developer.md#4-the-gate)).

The `check-updates` Claude Code skill reports which pins are outdated.

## 7. Security notes

This is a **development** environment:

- The credentials (`Administrator` / `admin`, MariaDB root `frappe`) are fixed
  and public. Every port binds to `127.0.0.1` only, both in the Vagrantfile and
  in `compose.yaml`. Keep it that way.
- In Podman, you can override the passwords for a new stack with
  `DB_ROOT_PASSWORD=… ADMIN_PASSWORD=… podman compose up -d`. They take effect
  when the site is created, not on an existing one.
- Developer mode is on, and the site allows running tests. Never expose this
  environment on a network.
