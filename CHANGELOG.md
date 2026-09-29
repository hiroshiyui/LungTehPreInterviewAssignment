# Changelog

All notable changes to this tutorial are recorded here, in
[Keep a Changelog](https://keepachangelog.com/) format. Versions follow
[Semantic Versioning](https://semver.org/) as they affect a learner following
the tutorial (see the `release-engineering` skill). Each release lists the
exact pins it was built and tested with, so `git checkout vX.Y.Z` rebuilds the
same environment.

## [Unreleased]

## [0.0.1] - 2026-09-29

The first tagged snapshot of the pre-interview assignment: Frappe `develop` on
a VirtualBox VM, or on Podman, built by one Ansible playbook, with the HR Cost
app on top.

### Added

- **Reproducible Frappe `develop` environment.** One idempotent Ansible
  playbook (roles `base` → `mariadb` → `nodejs` → `bench` → `site` →
  `bench_service` → `hr_cost_app` → `verify`) builds either:
  - a **VirtualBox VM** (`vagrant up`, `ansible_local`), which the assignment
    asks for;
  - a **Podman** stack (`podman compose up -d --build`) with the database,
    site files and job queue in named volumes.
- **The HR Cost app** (`apps/hr_cost`):
  - **Employee** and **Work Record** DocTypes, as the assignment specifies.
  - The **Daily HR Cost** report (total HR cost per day) and the **Monthly HR
    Cost** report (employees × months).
  - **Pay per the employment contract**, hourly or monthly, kept as a dated
    Pay History. Hourly work is costed at the rate valid on its date. A monthly
    salary accrues at salary ÷ 30 per calendar day. Employment dates bound
    both.
  - **Pay is confidential.** The HR Manager and HR User roles, with pay at
    permlevel 1, and permission-aware reports that honour roles, User
    Permissions and permlevels.
  - **Charts** on both reports, and an **HR Cost workspace** with number cards.
  - A **Download PDF** button on both reports: A4, with fonts for Chinese and
    Southeast Asian scripts.
  - **Staff from many countries.** Nationality (also a report filter), names
    in other writing systems, and work permit expiry warnings.
  - Polish: a drill-down from each day to its Work Records, Data Import and
    quick entry, Employee connections, and a namesake warning.
  - **Demo data**, with one demo user per HR role
    (`hr.manager@example.com` / `hr.user@example.com`, password `demo`).
- **Operations.** `scripts/backup.sh` and `scripts/restore.sh` for both
  solutions, and a systemd backup timer that is rendered and verified but
  never enabled.
- **One gate**, `tests/gate.sh`, with three modes:
  - `--quick`: static checks and 83 app tests;
  - full: a from-scratch build in a systemd container stand-in for the VM,
    then a re-run that must report `changed=0`;
  - `--compose`: persistence across container recreation, and a backup →
    restore round trip.
- **Docs.** The tutorial README (one chapter per hosting solution, with
  screenshots), plus `docs/ops.md`, `docs/developer.md`,
  `docs/troubleshooting.md` and `docs/todos.md`. Also `CLAUDE.md` and project
  skills.
- **Reproducibility.** Every input is pinned:
  - container images by digest;
  - the Frappe commit;
  - the exact Node.js;
  - Frappe's Python packages, frozen in
    `ansible/roles/bench/files/python-constraints.txt` and checked by the
    `verify` role.

  Provisioning also answers Frappe's setup wizard (English, Taiwan,
  Asia/Taipei, TWD).

### Known gaps

- **Not yet built on real VirtualBox.** The VM path is verified in a systemd
  container stand-in that runs the same bootstrap and playbook. vboxsf, NAT
  port forwarding and the bento box itself are untested (`docs/todos.md`,
  Verification).
- Overtime for monthly-paid staff isn't modelled, the app's own labels aren't
  translated, and PDFs have no charts (`docs/todos.md`).

### Pinned versions

| Input | Version |
| --- | --- |
| Vagrant box | `bento/ubuntu-24.04` `202510.26.0` |
| Ubuntu image (frappe image, test container) | `docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3` |
| MariaDB image | `docker.io/library/mariadb:10.11@sha256:7f22313fc130a377a44999965bcb0a08dd5b21e8502824c1b864f792f9bc66ab` |
| redis image | `docker.io/library/redis:7.2-alpine@sha256:29e8589c3f9ba699b5f7aa4b3c7733c58852a3626439e619aa0ee78de08c6ca0` |
| ansible-core | `2.21.4` |
| uv | `0.12.20` |
| Python | `3.14` (3.14.7 via uv 0.12.20) |
| Node.js | `24.21.0` (NodeSource `24.21.0-1nodesource1`) |
| yarn | `1.22.22` |
| frappe-bench | `5.31.0` |
| Frappe | `develop` @ `85e1148ec7c87bcd5939457a6adc3d9774020dcb` (`__version__` `17.0.0-dev`) |
| Frappe's Python packages | 145 pins in `ansible/roles/bench/files/python-constraints.txt` |
| hr_cost | `0.0.1` |

[Unreleased]: https://github.com/hiroshiyui/LungTehPreInterviewAssignment/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/hiroshiyui/LungTehPreInterviewAssignment/releases/tag/v0.0.1
