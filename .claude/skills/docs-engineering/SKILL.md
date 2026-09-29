---
name: docs-engineering
description: Audit and update all documentation of this Frappe onboarding project so it matches the code and works as a beginner tutorial — README (both paths: Vagrant VM and podman compose; setup procedure vs the Ansible roles; version table vs pins), docs/ops.md, docs/developer.md, docs/troubleshooting.md, docs/todos.md, CLAUDE.md, the app README, skills, and in-code "why" comments — with an eye for beginner readability.
---

In this project **the documentation is the product**. The assignment asked for "please
document your setup procedure", and the repo is kept as a long-term **onboarding tutorial**.
A doc that is out of step with the code is worse than no doc: a beginner will follow it,
fail, and not know why.

Read the docs as a newcomer would: someone who has never used Vagrant, podman, Ansible or
Frappe, and is copying commands one at a time. There are **two hosting solutions**, each with
its own README chapter (3: VirtualBox, 4: Podman), and every instruction must say which one
it's for.

| Doc | Audience and job |
|-----|------------------|
| `README.md` | the entry point: ch. 1 choose a hosting solution, ch. 2 shared roles/pins/URLs, ch. 3 VirtualBox (procedure in 3.3), ch. 4 Podman (build, storage), ch. 5 the app |
| `docs/ops.md` | running it: lifecycle, storage (where data lives), backup, restore, scheduled backups, upgrades, security notes |
| `docs/developer.md` | changing it: mental model, app rules, provisioning rules, the gate matrix, the "deliberately odd" table |
| `docs/troubleshooting.md` | symptom → cause → fix tables, grouped by path |
| `docs/todos.md` | known gaps, most important first; "Decided against" with reasons |
| `CLAUDE.md` | Claude Code's condensed view: commands and invariants |

---

## Step 1 — Audit accuracy, file by file

Check every item against the **current code**, without exception:

- **`README.md`**
  - **Chapter 1's comparison table and sections 3.1–3.2 / 4.1–4.2**: the requirements,
    start commands and provider install hints for each solution still work. Each
    solution's content stays inside its own chapter; shared content goes in chapter 2.
  - **Version tables** (chapter 2 shared, 3.1 VirtualBox, 4.1 Podman): each row matches its pin in `Vagrantfile`,
    `ansible/requirements.txt`, `ansible/group_vars/all.yml`, `compose.yaml` or
    `compose/Containerfile`, and the "why" column still holds (the Python/Node floors
    match the pinned frappe commit).
  - **Section 3.3, setup procedure**: one subsection per role, **in `site.yml` order**. Each
    manual command matches what the role actually does: same flags, same paths, same order.
    Diff them mentally task by task. This is the highest-value check in the whole skill.
    Section 4.3 lists every `deploy_target == 'container'` difference, and chapter 2's role
    table marks which roles run where; grep the roles for
    `deploy_target` and check each one is covered.
  - **Quick start and URLs**: Frappe 17 serves the desk under `/desk/...`. Check the site
    name, the credentials and the host ports (8000, 9000, and the harness's 18000).
  - **Repository layout**: matches the tree, and new top-level dirs or files are listed.
- **`docs/ops.md`**: the lifecycle tables for both paths; the **storage table** matches
  the volumes in `compose.yaml` and what they hold; the backup and restore commands match
  `scripts/backup.sh` / `restore.sh` options; the timer section matches `ops/systemd/` and
  `scripts/install-backup-timer.sh`, and still says that nothing enables the timer.
- **`docs/developer.md`**: the role order, the build/run tag split, the gate matrix (which
  change → which gate), the "deliberately odd" table, and the skills table.
- **`docs/troubleshooting.md`**: every row still describes a real symptom with a working
  fix. Remove rows whose cause has been fixed for good; add rows for failures you met.
- **`docs/todos.md`**: finished items are removed; newly discovered gaps are added.
- **`CLAUDE.md`**: commands still run, the role order and architecture notes are current,
  and the app conventions still hold.
- **`apps/hr_cost/README.md`**: the fields, business rules, report behaviour and commands.
- **In-code comments**: every non-obvious line carries its *why*. The canonical ones must
  survive refactors:
  - the NAT bind address;
  - the world-writable cwd `ansible.config_file`;
  - the shared-folder wait;
  - the Socket.IO port;
  - the pinned-commit-as-local-branch trick;
  - the rate snapshot;
  - the service-before-app role order;
  - `new-site --force` in containers;
  - `keep-id` + `user: root`;
  - backups written outside the volumes.
- **Skills** under `.claude/skills/`: file paths, commands and role names they cite still
  exist.

Verify commands rather than trust them. Anything cheap to run (`grep` for a pin, the
`bench` subcommand `--help`, a URL in the running test container) should be run.

## Step 2 — Audit beginner readability

- **Every step says what it does and why**, before the command, in one sentence. Jargon
  (bench, site, DocType, idempotent, provisioner) is explained on first use or linked to its
  official doc.
- **Commands are copy-pasteable**: no `$` prompts, placeholders marked `<like-this>` and
  explained, and it's clear *where* each command runs (host, `vagrant ssh`, which directory,
  which user).
- **Expected outcomes are stated**: what success looks like ("prints `pong`", "report shows
  one row per day"), so a learner can tell they're on track.
- **Failure paths exist**: the common first-run failures (port in use, not enough RAM,
  VirtualBox/kernel mismatch, interrupted `bench init`) are in Troubleshooting.
- **Accessible Markdown**: a heading hierarchy with no skipped levels, and descriptive link
  text (not "click here"). Tables have header rows. Code blocks carry a language tag
  (`bash`, `yaml`), so they render and read correctly in screen readers and on GitHub.
- Keep it **short enough to finish**. Move deep-dive material to a linked section rather
  than growing the main path.

## Step 3 — Revise

Fix everything that is stale, missing or confusing. When code changes, update the doc **in
the same change**: new role → new section 3.3 subsection plus a row in chapter 2's role table; new pin → a version-table row; new
failure mode found → a troubleshooting row. Never leave a doc describing behaviour that has
been removed.

## Step 4 — Verify

- Run `tests/gate.sh --quick` (it validates the shell scripts, the app JSON and lint, and
  runs the tests).
- If section 3.3 changed, run the changed manual commands in the test container
  (`podman exec -it -u vagrant frappe-dev-test bash`) to prove they work as written.
- If `docs/ops.md` commands changed, run them against a running compose stack. Use
  `--dry-run` for restore and backup where it exists, and never enable the backup timer.

## Step 5 — Commit

Commit documentation changes by topic, e.g. `docs(readme): sync setup procedure with bench
role` or `docs(claude): document gate script`. Don't mix unrelated doc changes, or docs with
code, unless the doc describes that exact code change.
