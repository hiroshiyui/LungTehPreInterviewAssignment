# Frappe (develop) + HR Cost app: a reproducible dev environment

Pre-interview assignment, kept as a long-term **onboarding tutorial**:

1. Install the **development version of [Frappe](https://github.com/frappe/frappe)**
   on a **VirtualBox VM**, and document the setup procedure.
2. Build an app on top of Frappe with an **Employee** DocType (Employee Name,
   Hourly Rate), a **Work Record** DocType (Employee Name, Hours Worked, Date),
   and a **report showing the total HR cost for each day**.

Everything is a reproducible build. Every version that affects the result is
pinned, including the exact Frappe `develop` commit, and one command rebuilds
the same environment from scratch.

More documentation:

- [docs/ops.md](docs/ops.md): run, stop, storage, backup and restore, scheduled backups, upgrades.
- [docs/developer.md](docs/developer.md): working on the app and the provisioning, tests, and the gate.
- [docs/troubleshooting.md](docs/troubleshooting.md): known problems and their fixes.
- [docs/todos.md](docs/todos.md): known gaps and planned work.

---

## Contents

- [1. Choose a hosting solution](#1-choose-a-hosting-solution)
- [2. What both solutions share](#2-what-both-solutions-share)
- [3. VirtualBox (Vagrant)](#3-virtualbox-vagrant)
- [4. Podman (compose)](#4-podman-compose)
- [5. The HR Cost app](#5-the-hr-cost-app)
- [6. Repository layout](#6-repository-layout)

---

## 1. Choose a hosting solution

Pick **one** chapter and follow it from top to bottom. Both solutions give you
the same Frappe site and app at **http://localhost:8000** (login
**Administrator / admin**). They are built by the **same Ansible playbook**.

| | [**Chapter 3: VirtualBox (Vagrant)**](#3-virtualbox-vagrant) | [**Chapter 4: Podman (compose)**](#4-podman-compose) |
| --- | --- | --- |
| What you get | one Ubuntu 24.04 VM with everything inside | 4 containers: `frappe`, `mariadb`, `redis-cache`, `redis-queue` |
| Start with | `vagrant up` | `podman compose up -d --build` |
| Host needs | VirtualBox 7.1+, Vagrant 2.3+ | podman 4+, `podman-compose` |
| Works on | Linux, macOS, Windows | Linux (podman-specific features) |
| Data lives in | the VM's disk | named volumes; backups on the host |
| Choose it when | you want what the assignment asks for, or an isolated full machine | you can't run VirtualBox, or you want a lighter, faster setup |

## 2. What both solutions share

**One playbook.** `ansible/site.yml` runs these roles, in this order. Each role
is one step of the setup procedure:

| Role | Does | VirtualBox | Podman |
| --- | --- | --- | --- |
| `base` | OS packages | ✔ | ✔ (image build) |
| `mariadb` | local MariaDB, `utf8mb4` | ✔ | – (the `mariadb` service) |
| `nodejs` | Node.js 24 + yarn | ✔ | ✔ (image build) |
| `bench` | Python 3.14, bench, the pinned frappe commit, `bench init` | ✔ | ✔ (image build) |
| `site` | `bench new-site` | ✔ | ✔ (each container start) |
| `bench_service` | `bench start` as a systemd service | ✔ | – (the container's entrypoint) |
| `hr_cost_app` | links, installs and migrates the app; loads demo data | ✔ | ✔ (each container start) |
| `verify` | API checks + the app's unit tests | ✔ | on demand (`tests/gate.sh --compose`) |

A single variable, `deploy_target` (`vm` or `container`), switches the few
places where the two solutions differ.

**Pinned versions.** Each pin has exactly one home:

| Component | Version | Pinned in | Why |
| --- | --- | --- | --- |
| Frappe | `develop` @ **85e1148ec7c8** (17.0.0-dev) | `ansible/group_vars/all.yml` | the "development version", pinned to a commit for reproducibility |
| frappe-bench | **5.31.0** | `group_vars/all.yml` | Frappe's CLI |
| Python | **3.14** (3.14.7 via uv) | `group_vars/all.yml` | Frappe develop requires `>=3.14,<3.15`; Ubuntu ships 3.12 |
| uv | **0.12.20** | `group_vars/all.yml` | installs Python 3.14 and bench, and builds the bench venv (checksum-verified download) |
| Node.js | **24.x** (24.21.0 at time of writing, NodeSource) | `group_vars/all.yml` | Frappe develop requires `node >=24` |
| yarn | **1.22.22** | `group_vars/all.yml` | used by bench to build assets |
| ansible-core | **2.21.4** | `ansible/requirements.txt` | installed into `/opt/ansible` in the VM or the image |
| Ubuntu | 24.04 LTS | `Vagrantfile` (box) / `compose/Containerfile` (base image) | the same OS, so the same roles apply |

The versions specific to one solution (the box, the MariaDB and redis images)
are listed in that solution's chapter.

To build against the *current* tip of `develop` instead of the pinned commit,
set `frappe_commit: ""` in `ansible/group_vars/all.yml`. To move the pin, put a
new SHA there (`git ls-remote https://github.com/frappe/frappe refs/heads/develop`).

**URLs** (identical for both solutions):

| What | URL |
| --- | --- |
| Desk | http://localhost:8000/desk |
| Employees | http://localhost:8000/desk/employee |
| Work Records | http://localhost:8000/desk/work-record |
| Daily HR Cost report | http://localhost:8000/desk/query-report/Daily%20HR%20Cost |
| Monthly HR Cost report | http://localhost:8000/desk/query-report/Monthly%20HR%20Cost |

> Frappe 17 serves the desk under `/desk`. The older `/app/...` URLs still
> work and redirect there.

---

## 3. VirtualBox (Vagrant)

The solution the assignment asks for: **Vagrant** creates a VirtualBox VM, and
**Ansible** provisions everything inside it.

### 3.1 Host requirements

| | |
| --- | --- |
| VirtualBox | 7.1 or newer (x86_64 or Apple-silicon arm64 host) |
| Vagrant | 2.3 or newer |
| Resources | 2 vCPU and 4 GB RAM for the VM (adjustable), about 10 GB disk |
| Network | internet access during `vagrant up` (apt, GitHub, PyPI, npm) |

Ansible does **not** need to be installed on the host. The VM installs a
pinned `ansible-core` and runs the playbook against itself (Vagrant's
`ansible_local` provisioner), so the build works the same from Linux, macOS
and Windows.

Pinned for this solution: the box, `bento/ubuntu-24.04` **202510.26.0**, in the
`Vagrantfile`. It has VirtualBox guest additions built in. MariaDB (10.11) and
Redis (7.x) come from Ubuntu 24.04's packages.

### 3.2 Quick start

```bash
git clone <this repository> && cd <repository>
vagrant up                 # first run: 15–25 min, mostly `bench init`
```

When it finishes, the last Ansible task prints the URLs (see
[chapter 2](#2-what-both-solutions-share)). Log in as **Administrator / admin**.

Environment variables read by the `Vagrantfile`:

```bash
FRAPPE_VM_CPUS=4 FRAPPE_VM_MEMORY=6144 vagrant up   # a bigger VM
FRAPPE_HOST_PORT=8080 vagrant up                     # if host port 8000 is taken
ANSIBLE_VERBOSE=v vagrant provision                  # more Ansible output
```

### 3.3 Setup procedure, step by step

This is exactly what `vagrant up` automates. Each step names the role that
implements it, so you can also follow the procedure by hand on any Ubuntu
24.04 machine.

#### 3.3.1 Create the VM (`Vagrantfile`)

* A VirtualBox VM from the pinned `bento/ubuntu-24.04` box, hostname `frappe-dev`.
* Port forwards, bound to 127.0.0.1 on the host: guest `8000` → host `8000`
  (web) and guest `9000` → host `9000` (realtime/Socket.IO).
* The project directory is shared into the VM at `/vagrant`.

#### 3.3.2 Install Ansible in the guest (`scripts/bootstrap-ansible.sh`)

```bash
sudo apt-get install -y python3-venv python3-apt
sudo python3 -m venv /opt/ansible
sudo /opt/ansible/bin/pip install -r /vagrant/ansible/requirements.txt   # ansible-core==2.21.4
```

Vagrant then runs `ansible/site.yml` inside the guest, with
`frappe_user=vagrant`.

#### 3.3.3 OS packages (role `base`)

```bash
sudo apt-get install -y build-essential pkg-config git curl file ca-certificates gnupg acl \
    libffi-dev libssl-dev libmariadb-dev mariadb-client redis-server cron rsync xz-utils python3-debian
sudo systemctl disable --now redis-server     # bench starts its own redis processes
echo 'fs.inotify.max_user_watches = 524288' | sudo tee /etc/sysctl.d/60-frappe-inotify.conf
sudo sysctl --system                          # for the asset watcher
```

#### 3.3.4 MariaDB (role `mariadb`)

```bash
sudo apt-get install -y mariadb-server mariadb-client
sudo tee /etc/mysql/mariadb.conf.d/99-frappe.cnf <<'EOF'
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
[mysql]
default-character-set = utf8mb4
EOF
sudo systemctl restart mariadb
# Keep socket auth for the OS root user and add a password, so that
# `bench new-site` (running as a normal user) can connect as DB root:
sudo mariadb -e "ALTER USER 'root'@'localhost' IDENTIFIED VIA unix_socket
                 OR mysql_native_password USING PASSWORD('frappe'); FLUSH PRIVILEGES;"
```

#### 3.3.5 Node.js 24 and yarn (role `nodejs`)

```bash
# Add the NodeSource apt repository (deb822 format, signed by the NodeSource key), then:
sudo apt-get install -y nodejs          # 24.x
sudo npm install --global yarn@1.22.22
```

#### 3.3.6 Python 3.14, bench and Frappe (role `bench`)

All of this runs as the bench user (`vagrant` in the VM):

```bash
# uv is a static binary (sha256-verified) → /usr/local/bin/uv
uv python install 3.14
uv tool install --python 3.14 frappe-bench==5.31.0        # → ~/.local/bin/bench

# Fetch the pinned develop commit into a local repo. bench can only clone
# branches, so the pinned commit is named `develop` locally.
mkdir -p ~/src/frappe && cd ~/src/frappe
git init && git remote add origin https://github.com/frappe/frappe.git
git fetch --depth 1 origin 85e1148ec7c87bcd5939457a6adc3d9774020dcb
git checkout -B develop FETCH_HEAD

# Create the bench: this clones frappe, creates env/ with Python 3.14,
# installs the Python and JS dependencies and builds the assets. --dev turns on
# developer_mode and installs Frappe's dev/test dependencies.
cd ~
bench init --frappe-path ~/src/frappe --frappe-branch develop \
           --python 3.14 --dev frappe-bench
git -C frappe-bench/apps/frappe remote set-url upstream https://github.com/frappe/frappe.git
```

#### 3.3.7 The site (role `site`)

```bash
cd ~/frappe-bench
bench new-site hrcost.localhost --db-root-username root --db-root-password frappe \
      --admin-password admin --mariadb-user-host-login-scope=localhost --set-default
bench --site hrcost.localhost set-config allow_tests 1 --parse
```

#### 3.3.8 Run the bench as a service (role `bench_service`)

`bench start` is wrapped in a systemd unit
(`/etc/systemd/system/frappe-bench.service`), so the VM serves Frappe after
every boot. It runs the web server, the realtime server, background workers,
the scheduler, redis cache and queue, and the asset watcher. Two details
matter in a VM:

* `FRAPPE_BIND_ADDR=0.0.0.0`: `bench serve` listens on 127.0.0.1 by default,
  which VirtualBox NAT port forwarding cannot reach.
* `ExecStartPre` waits for `/vagrant/apps/hr_cost`, because the shared folder
  is mounted only after boot.

```bash
sudo systemctl enable --now frappe-bench
journalctl -u frappe-bench -f        # follow the logs
```

#### 3.3.9 Install the custom app (role `hr_cost_app`)

The app's source lives in this repository (`apps/hr_cost`). The bench's
`apps/hr_cost` is a **symlink to the shared folder** instead of a copy. That
keeps the repo as the single source of truth: you edit on the host, and
DocType changes saved in the Desk (developer mode) are written straight back
into the repo.

```bash
cd ~/frappe-bench
ln -s /vagrant/apps/hr_cost apps/hr_cost
uv pip install --python env/bin/python -e apps/hr_cost
echo hr_cost >> sites/apps.txt
bench --site hrcost.localhost install-app hr_cost    # on later runs: bench migrate
bench --site hrcost.localhost execute hr_cost.demo.create_demo_data   # sample data
```

#### 3.3.10 Verify (role `verify`)

The playbook ends by checking its own work:

1. `GET /api/method/ping` returns `pong`.
2. It logs in as Administrator and runs the **Daily HR Cost** report through
   the REST API (`frappe.desk.query_report.run`), and checks that the report
   returns rows.
3. It runs the app's unit tests: `bench --site hrcost.localhost run-tests --app hr_cost`.

### 3.4 Operating it

| Task | Command |
| --- | --- |
| Re-apply provisioning (idempotent) | `vagrant provision` |
| Shell inside the VM | `vagrant ssh` |
| Stop / start | `vagrant halt` / `vagrant up` (the bench starts at boot) |
| Back up the site to `./backups` | `scripts/backup.sh --target vm` |
| Rebuild from nothing (**deletes all data**) | `vagrant destroy -f && vagrant up` |

The full details (logs, restore, scheduled backups, upgrades) are in
[docs/ops.md](docs/ops.md).

---

## 4. Podman (compose)

The same Frappe environment as four containers instead of a VM. The frappe
image is built by the same Ansible roles as chapter 3, and all state is kept in
named volumes.

### 4.1 Host requirements

| | |
| --- | --- |
| podman | 4 or newer (rootless is fine) |
| compose provider | `podman-compose`, so that `podman compose` works |
| Resources | about 4 GB RAM free during the image build, about 6 GB disk |
| Network | internet access during the build (apt, GitHub, PyPI, npm, image registry) |

```bash
sudo apt install podman-compose            # Debian/Ubuntu; Fedora: sudo dnf install podman-compose
# or, from PyPI:  uv tool install podman-compose   (or pipx install podman-compose)
podman compose version                     # should print the podman-compose version
```

Pinned for this solution, in `compose.yaml`: `docker.io/library/mariadb:10.11`
and `docker.io/library/redis:7.2-alpine`. The frappe image is built from
`docker.io/library/ubuntu:24.04` (`compose/Containerfile`).

### 4.2 Quick start

```bash
git clone <this repository> && cd <repository>
podman compose up -d --build     # first build: about 10 min (bench init runs in the image build)
podman compose logs -f frappe    # first start: creates the site, installs the app, starts bench
```

Open **http://localhost:8000** once the log shows `Running on http://…:8000`,
and log in as **Administrator / admin**.

Environment variables read by `compose.yaml`:

```bash
FRAPPE_HOST_PORT=8080 podman compose up -d                    # if host port 8000 is taken
DB_ROOT_PASSWORD=… ADMIN_PASSWORD=… podman compose up -d      # other dev passwords (new stacks only)
```

### 4.3 How it is built

| Service | Image | Role |
| --- | --- | --- |
| `frappe` | built from `compose/Containerfile` | the bench: web, realtime, workers, scheduler, asset watcher |
| `mariadb` | official `mariadb:10.11` | the database, started with the same `utf8mb4` settings as step 3.3.4 |
| `redis-cache` | official `redis:7.2-alpine` | cache, deliberately not persisted |
| `redis-queue` | official `redis:7.2-alpine` | background job queue, persisted |

1. **Image build** (`compose/Containerfile`): installs the pinned ansible-core,
   then runs the playbook's `base`, `nodejs` and `bench` roles with
   `ansible/vars/container.yml`. These are steps 3.3.3, 3.3.5 and 3.3.6, with
   these differences:
   - `bench init` gets `--no-procfile --skip-redis-config-generation`;
   - `common_site_config.json` points at `redis://redis-cache:6379` and
     `redis://redis-queue:6379`;
   - the Procfile has no redis processes;
   - no `redis-server` package (redis runs as its own services), and no
     systemd or sysctl changes (containers have no systemd and share the host kernel).
2. **Every container start** (`compose/entrypoint.sh`):
   1. wait until MariaDB answers;
   2. run the `site` and `app` roles. The first start creates the site with
      `--db-host mariadb --mariadb-user-host-login-scope=%`. Later starts only
      re-link the app and run `bench migrate`;
   3. `exec runuser -u frappe -- bench start`.
3. **The repository** is bind-mounted at `/workspace`, and the bench's
   `apps/hr_cost` links there. As in the VM, app edits on the host and DocTypes
   saved in the Desk land in this repo. `userns_mode: keep-id` makes those files
   belong to you.
4. **Ports** bind to 127.0.0.1 only: `8000` (web) and `9000` (realtime).
   MariaDB and redis publish no ports.

### 4.4 Storage and backups

All state lives in **named volumes**, so containers can be removed, recreated
or rebuilt without losing anything:

| Volume | Holds |
| --- | --- |
| `frappe-dev_db-data` | the MariaDB datadir: the site's database |
| `frappe-dev_site-data` | `sites/hrcost.localhost`: `site_config.json` (DB credentials, encryption key), uploaded public and private files |
| `frappe-dev_queue-data` | the redis job queue |

- `podman compose down` **keeps** the volumes. `podman compose down -v`
  **deletes** them.
- `db-data` and `site-data` belong together: keep both, or wipe both.
- Code and built assets are *not* in a volume. They come from the image, so a
  rebuild never leaves stale assets behind.

Backups are written **to the host**, outside the volumes they protect:

```bash
scripts/backup.sh                                     # → ./backups/<timestamp>/ (DB + files + config)
scripts/restore.sh --from backups/<timestamp> --yes   # destructive; try --dry-run first
scripts/install-backup-timer.sh                       # dry run of the daily systemd timer (never enabled for you)
```

[docs/ops.md](docs/ops.md) explains restore, disaster recovery and the timer.

### 4.5 Operating it

| Task | Command |
| --- | --- |
| Status / logs | `podman compose ps` / `podman compose logs -f frappe` |
| Shell in the frappe container | `podman compose exec -u frappe frappe bash` |
| Stop / start | `podman compose stop` / `podman compose start` |
| Apply a rebuilt image (keeps data) | `podman compose down && podman compose up -d --build` |
| Wipe everything, **including data** | `podman compose down -v` |

`podman-compose` does not recreate running containers when the image
changes. Always use `down`, then `up -d --build`. The full details are in
[docs/ops.md](docs/ops.md).

---

## 5. The HR Cost app

[`apps/hr_cost/README.md`](apps/hr_cost/README.md) has the full
description. In short:

* **Employee**: `employee_name` (Data, required), `hourly_rate` (Currency,
  required, > 0), and an **Hourly Rate History** (dated rates). Named
  `EMP-#####` and displayed by name in links.
* **Work Record**: `employee` (Link → Employee) with the fetched
  `employee_name`, `date` (default today, never in the future), and
  `hours_worked` (> 0, and at most 24 h per employee per day), plus read-only
  `hourly_rate` (the rate valid on that date) and `cost`, computed on save.
* **Daily HR Cost** (a Script Report on Work Record): one row per date with the
  number of employees, the total hours and the **total HR cost**. It defaults
  to the current month, can be filtered by employee, and shows a bar chart and
  period totals (total cost, total hours, days with work, average cost per
  day). "Show days without work" adds zero rows, so the chart's time axis has
  no gaps.
* **Monthly HR Cost** (a Script Report on Work Record): the assignment's
  "calculate monthly". One row per employee and one column per month, with the
  employee's total hours and cost and a total row. It defaults to the current
  year and can be filtered by employee.

Design decisions:

* **Rates are dated, and each Work Record is costed at the rate valid on its
  date.** A pay raise is a new dated row in the employee's history, so it never
  rewrites the cost of earlier work, and work entered late is still costed at
  the rate that applied on its day. Correcting a rate re-costs the affected
  records. The cost is stored on each record, so both reports are simple
  `GROUP BY` sums (by date, or by employee and month).
* The DocType and Report JSON and the boilerplate were **generated by Frappe
  itself**: `bench new-app`, then the DocTypes were created in developer mode.
  That keeps them in the exact v17 format. The business logic, the report and
  the tests were written on top.
* Frappe core has no `Employee` DocType, so the required name is free. It would
  clash with ERPNext/HRMS, which aren't installed here.

## 6. Repository layout

```
Vagrantfile                      chapter 3: VM definition (VirtualBox) + provisioners
compose.yaml                     chapter 4: services, volumes, ports
compose/                         chapter 4: frappe image (Containerfile) + entrypoint
scripts/bootstrap-ansible.sh     installs the pinned ansible-core (VM, image)
scripts/backup.sh, restore.sh    site backup/restore (both solutions), see docs/ops.md
scripts/install-backup-timer.sh  renders/verifies the systemd backup timer; never enables it
ops/systemd/                     backup timer and service templates
ansible/
  site.yml                       the play (roles in chapter 2)
  requirements.txt               ansible-core pin
  group_vars/all.yml             every other shared pin and setting
  vars/container.yml             chapter 4 overrides (deploy_target: container)
  roles/…                        one role per step in section 3.3
apps/hr_cost/                    the custom Frappe app (source of truth)
tests/gate.sh                    the project gate (see docs/developer.md)
tests/container/                 podman-based stand-in for the VM, used by the gate
docs/                            ops, developer, troubleshooting, todos
```
