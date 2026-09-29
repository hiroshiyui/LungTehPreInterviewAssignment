---
name: commit-and-push
description: Stage, commit, and push changes of this Frappe onboarding project (Vagrant VM and podman compose paths) with a well-formed Conventional Commit message, after the right gate has passed (quick for app/docs, full + compose for provisioning, compose for compose/backup changes).
---

**Default: land directly on `main`.** Unless the user asks to keep the work on a feature
branch, commit to `main` and push it (fast-forwarding `main` if the work is on a branch).
Only stay on a feature branch when explicitly told to.

Git history is part of the tutorial: learners read `git log` to see how the project grew.
Keep commits small, topical and explained.

Steps:

1. **Stage deliberately.** Stage only the files for the current topic, and never
   `git add -A` when unrelated changes are present. Never stage `.vagrant/` (it holds the
   VM's private SSH key), `backups/` (sets contain the site's encryption key and DB
   password), `site_config.json`, `__pycache__/` or logs. Check
   `git status --short` before committing.

2. **Run the right gate first**, and don't commit a red tree (the matrix is in
   `docs/developer.md`, "The gate"):
   - Only `apps/hr_cost/**` or docs changed: `tests/gate.sh --quick`.
   - `ansible/**`, `scripts/bootstrap-ansible.sh`, `Vagrantfile` or `tests/container/**`
     changed: `tests/gate.sh` **and** `tests/gate.sh --compose`, because both paths run
     the same roles.
   - `compose.yaml`, `compose/**`, `scripts/backup.sh`, `scripts/restore.sh` or
     `ops/systemd/**` changed: `tests/gate.sh --compose`.
   - Never enable the backup timer as part of testing; `scripts/install-backup-timer.sh`
     (a dry run by default) is the check.

3. **Commit** with a [Conventional Commits](https://www.conventionalcommits.org/) message
   that explains *why*, not just *what*. Typical scopes:
   - `vagrant`
   - `compose`
   - `ansible` (or the role name: `bench`, `site`, `mariadb`, `nodejs`, `bench_service`,
     `hr_cost_app`, `verify`)
   - `ops` (backup, restore, timer)
   - `app` (the hr_cost app)
   - `report`
   - `docs`
   - `tests`
   - `deps` / `frappe` (pin moves)

   Examples:
   - `fix(bench): wait for the shared folder before starting bench`
   - `fix(compose): drop to the frappe user with runuser from /usr/sbin`
   - `feat(report): add employee filter to Daily HR Cost`
   - `build(frappe): move develop pin to 1a2b3c4`

4. **Push** to `origin`: `main` by default, or the feature branch only when asked. If
   `git remote` is empty (it is until a remote is added), stop after committing and tell the
   user to add one first.

5. **Verify** the push succeeded and that the local branch is in sync with the remote
   (`git status -sb` shows no ahead/behind).
