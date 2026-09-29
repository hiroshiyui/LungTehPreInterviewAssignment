# Troubleshooting

Find the symptom, apply the fix. If yours isn't here, check the logs first:

```bash
vagrant ssh -c 'journalctl -u frappe-bench -n 200'   # VirtualBox
podman compose logs --tail 200 frappe                 # Podman
```

When you solve a new problem, add a row here.

---

## Both paths

| Symptom | Cause | Fix |
| --- | --- | --- |
| The browser console shows `Failed to execute 'removeChild' on 'Node'` on the HR Cost workspace | a race in Frappe's chart library: an old chart's resize observer fires after its widget redrew | harmless; the charts are drawn correctly |
| "Download PDF" fails with `wkhtmltopdf` not found (or `No wkhtmltopdf executable found`) | the VM or image was built before the `base` role installed it | VirtualBox: `vagrant provision`; Podman: `podman compose down && podman compose up -d --build` (the image installs it) |
| Names print as empty boxes in a PDF (Chinese, Thai, Burmese, Khmer, …) | no font for that script on the server | the `base` role installs `fonts-noto-cjk` and `fonts-noto-core`: re-provision or rebuild the image; for a script they miss, add its font package there |
| `You do not have permission to access field: Employee.<field>` (e.g. `date_of_joining`) right after pulling new code | the code expects a field the site's database doesn't have yet: the site hasn't been migrated | Podman: `podman compose restart frappe` (every start migrates); VirtualBox: `vagrant provision`, or `bench --site hrcost.localhost migrate` in the VM |
| After login, a "Welcome" form asks for language, country, time zone and currency | Frappe's setup wizard, on a site that provisioning hasn't set up (for example one made by hand) | fill it in once, or run `bench --site <site> execute hr_cost.setup.complete_site_setup --kwargs '…'` (see README 3.3.9) |
| Amounts show `$` instead of TWD, and the country is empty | Frappe marked its setup wizard complete by itself (it does once any non-admin user exists), so nobody answered it | re-provision, or run `hr_cost.setup.complete_site_setup` as in README 3.3.9 |
| `http://localhost:8000` doesn't load right after start | the first start is still creating the site or migrating | wait for `Running on http://…:8000` in the logs |
| Page loads, but live updates / "realtime" don't work | host port 9000 is not reachable | keep 9000 free on the host; it can't be remapped (the browser connects to 9000) |
| `Cannot run bench migrate without the services running` | the bench's redis isn't up | VirtualBox: `sudo systemctl start frappe-bench`; Podman: `podman compose up -d` (the redis services) |
| DocType changes made in the repo don't show up | the site wasn't migrated | `bench --site hrcost.localhost migrate` (Podman: a restart migrates too) |
| Python change has no effect in background jobs | workers don't auto-reload | restart the bench (see [ops.md](ops.md#1-lifecycle)) |
| `/app/...` URLs redirect | Frappe 17 moved the desk to `/desk/...` | expected; use `/desk/...` |
| `run-tests` says tests aren't allowed | `allow_tests` is off for the site | `bench --site hrcost.localhost set-config allow_tests 1 --parse` |

## VirtualBox (Vagrant)

| Symptom | Cause | Fix |
| --- | --- | --- |
| Port 8000 already in use on the host | another service | `FRAPPE_HOST_PORT=8080 vagrant up` |
| `bench init` is killed / out of memory | VM too small | `FRAPPE_VM_MEMORY=6144 vagrant reload --provision` |
| Provisioning was interrupted during `bench init` | partial bench | re-run `vagrant provision`; the partial bench is removed automatically |
| Site not reachable after `vagrant up` | the service failed | `vagrant ssh -c 'systemctl status frappe-bench'` |
| Edits made on the host have no effect (Python or JS) | the VirtualBox shared folder doesn't deliver file-change notifications to the VM, so nothing reloads | `vagrant ssh -c 'sudo systemctl restart frappe-bench'`, or edit under `/vagrant` from inside the VM ([developer.md](developer.md#2-working-on-the-app)) |
| Service stuck in "activating" after boot | it waits for the shared folder (`/vagrant/apps/hr_cost`) | check that `/vagrant` is mounted: `vagrant reload` |
| VirtualBox won't start the VM on a very new Linux kernel | VirtualBox doesn't support the kernel yet | upgrade VirtualBox, or use the Podman solution |
| `[WARNING]: Ansible is being run in a world writable directory` | the vboxsf share | harmless: the Vagrantfile passes `ansible.config_file` explicitly |

## Podman (compose)

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Error: looking up compose provider failed` | no compose provider installed | `sudo apt install podman-compose` (or `uv tool install podman-compose`) |
| Rebuilt image, but the old behaviour persists | podman-compose keeps running containers | `podman compose down && podman compose up -d --build` |
| `Site hrcost.localhost already exists` | the site volume exists but `site_config.json` is missing | the playbook handles this (`--force`); if it persists, wipe both volumes together: `podman compose down -v` |
| The site can't connect to its database | `site-data` and `db-data` got out of step (one wiped) | restore from a backup ([ops.md](ops.md#4-restore)), or `podman compose down -v` for a fresh start |
| Files written by the container are owned by a strange uid | `userns_mode: keep-id` unsupported (old podman, or docker-compose as the provider) | use podman 4+ with podman-compose |
| `podman compose up --build` rebuilds from scratch after a small change | a change under `ansible/` invalidates the image layer that runs `bench init` | expected; it takes about 6–10 minutes |
| Port 8000 is taken | another service, or the Vagrant VM is running | `FRAPPE_HOST_PORT=8080 podman compose up -d`, or stop the other one |

## Backups and the timer

| Symptom | Cause | Fix |
| --- | --- | --- |
| `scripts/restore.sh` refuses to run | it's destructive | add `--yes` (or look first with `--dry-run`) |
| `--from must be an existing backups/<timestamp> directory` | the set is outside `./backups` | move it into `./backups/`; only that directory is visible inside the container/VM |
| Encrypted fields are unreadable after a disaster restore | the new site has a different `encryption_key` | copy it from `*-site_config_backup.json` into `site_config.json` ([ops.md](ops.md#4-restore)) |
| The timer never fires | it's not enabled (by design), or you're logged out | `systemctl --user list-timers`; enable it yourself, and see `loginctl enable-linger` |
| The timer's backup fails with `podman: command not found` / `podman-compose` missing | the minimal PATH of user units | the unit already adds `~/.local/bin`; check where your provider is installed |
