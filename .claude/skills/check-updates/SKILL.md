---
name: check-updates
description: Check every pinned input of this Frappe onboarding project (Vagrant VM and podman compose paths) for newer versions and advisories — the Vagrant box, the container images (ubuntu, mariadb, redis), ansible-core, uv, CPython 3.14, Node.js/yarn, frappe-bench, and the pinned frappe develop commit (including whether it raised its Python/Node requirements) — then report what is outdated, grouped by risk. Reports only; does not bump pins without confirmation.
---

The whole project rests on **pins**. Nothing auto-updates (there's no Dependabot and no
remote yet), so this skill is the only way pins move. A long-lived tutorial with stale
pins eventually stops building: boxes get deleted from Vagrant Cloud, old Node majors leave
NodeSource, and `develop` moves on. Check regularly.

Where the pins live:

| Pin | File |
|-----|------|
| `BOX_VERSION` (`bento/ubuntu-24.04`) | `Vagrantfile` |
| `ansible-core==…` | `ansible/requirements.txt` |
| `uv_version`, `python_version`, `nodejs_major`, `nodejs_version`, `yarn_version`, `bench_version`, `frappe_commit` | `ansible/group_vars/all.yml` |
| `mariadb:10.11@sha256:…`, `redis:7.2-alpine@sha256:…` | `compose.yaml` |
| `ubuntu:24.04@sha256:…` (image bases) | `compose/Containerfile` and `tests/container/Containerfile` (same digest) |
| Frappe's Python packages (145 `==` lines) | `ansible/roles/bench/files/python-constraints.txt` (generated) |

This skill **reports**. Don't edit pins or run an upgrade without the user confirming the
specific bumps.

---

## Step 1 — Collect current vs latest

```bash
# Current pins
grep -E '^BOX_VERSION' Vagrantfile
cat ansible/requirements.txt
grep -E '^(uv_version|python_version|nodejs_major|nodejs_version|yarn_version|bench_version|frappe_commit):' ansible/group_vars/all.yml
grep -E 'image: |^FROM' compose.yaml compose/Containerfile tests/container/Containerfile

# Current index digest behind each tag (compare with the pinned @sha256:…)
for ref in library/ubuntu:24.04 library/mariadb:10.11 library/redis:7.2-alpine; do
  repo=${ref%%:*}; tag=${ref##*:}
  tok=$(curl -fsS "https://auth.docker.io/token?service=registry.docker.io&scope=repository:$repo:pull" | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
  curl -fsSI -H "Authorization: Bearer $tok" -H "Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json" \
    "https://registry-1.docker.io/v2/$repo/manifests/$tag" | grep -i docker-content-digest | sed "s|^|$ref |"
done

# Newest NodeSource build of the pinned major (in the test container)
podman exec frappe-dev-test apt-cache madison nodejs | head -3

# Container images: newest patch tag in each pinned series (read-only; pulls nothing)
podman search --list-tags --limit 5000 docker.io/library/mariadb | awk '{print $2}' | grep -E '^10\.11\.[0-9]+$' | sort -V | tail -1
podman search --list-tags --limit 5000 docker.io/library/redis   | awk '{print $2}' | grep -E '^7\.2\.[0-9]+-alpine$' | sort -V | tail -1
podman image inspect docker.io/library/mariadb:10.11 --format '{{index .Config.Labels "org.opencontainers.image.version"}}'   # what's pulled locally

# PyPI: ansible-core, uv, frappe-bench (latest + requires_python)
for p in ansible-core uv frappe-bench; do curl -s https://pypi.org/pypi/$p/json | python3 -c "import json,sys;i=json.load(sys.stdin)['info'];print('$p',i['version'],i['requires_python'])"; done

# yarn classic
curl -s https://registry.npmjs.org/yarn/latest | python3 -c 'import json,sys;print("yarn",json.load(sys.stdin)["version"])'

# frappe develop tip vs the pin, and how far behind the pin is
git ls-remote https://github.com/frappe/frappe refs/heads/develop
gh api repos/frappe/frappe/compare/<frappe_commit>...develop --jq '.ahead_by'   # if gh is available
```

## Step 2 — Check the frappe requirements *at the candidate commit*

Frappe `develop` periodically raises its floor. Check the **candidate** commit, not the
current one:

```bash
C=<candidate-sha>
curl -s https://raw.githubusercontent.com/frappe/frappe/$C/pyproject.toml | grep requires-python
curl -s https://raw.githubusercontent.com/frappe/frappe/$C/package.json | grep -A2 '"engines"'
curl -s https://raw.githubusercontent.com/frappe/frappe/$C/frappe/__init__.py | grep __version__
```

- A new **Python minor** (e.g. `>=3.15`) means bumping `python_version`, plus the README's
  version table (chapter 2) and section 3.3.
- A new **Node major** means bumping `nodejs_major`, after checking that NodeSource publishes
  `node_<N>.x`.
- A major `__version__` change (17 → 18) means reading the Frappe changelog for breaking
  changes in DocType JSON, `frappe.qb`, report APIs and desk URLs (v17 moved `/app` →
  `/desk`).

## Step 3 — Compatibility links to check

- **ansible-core ↔ guest Python**: the control node is the guest's system Python (Ubuntu
  24.04 = 3.12). A new ansible-core whose `requires_python` excludes 3.12 can't be installed
  by `bootstrap-ansible.sh`.
- **ansible-core ↔ ansible-lint**: after a bump, re-run `ansible-lint` because rules and
  deprecations shift.
- **MariaDB image ↔ VM MariaDB**: both paths should run the same MariaDB series (Ubuntu
  24.04 ships 10.11). Moving the compose image to 11.x alone makes the paths diverge;
  report it as a project decision.
- **Image digests**: the tags `mariadb:10.11`, `redis:7.2-alpine` and `ubuntu:24.04` get
  patch (and security) updates upstream, but the pinned digest doesn't move. Report when
  the tag's current digest differs from the pin. Applying it means replacing the digest,
  in both Containerfiles for Ubuntu, then running the full and compose gates. That's an
  *update* and needs confirmation like any other.
- **Python constraints ↔ `frappe_commit`**: moving the Frappe pin usually needs a
  regenerated `python-constraints.txt`, because the old versions may not satisfy the new
  commit and `bench init` then fails to resolve. The sequence is: move the pin, drop the
  conflicting lines, run a green `tests/gate.sh`, run `scripts/freeze-python-deps.sh`,
  then run the gates again. Report package updates within the constraints as one
  "refresh the Python lock" item, not package by package.
- **Box ↔ VirtualBox**: new bento boxes ship newer Guest Additions. Mention that users with
  older VirtualBox may need an upgrade.
- **Ubuntu base**: this project stays on the 24.04 LTS box. Moving to a new LTS (26.04) is a
  *project decision*, not a routine bump: it changes MariaDB, redis and the system Python.
  Report it separately.

---

## Reporting

One consolidated list, grouped by **risk**:

| Priority | Criteria |
|----------|----------|
| **Blocking** | A pinned box version deleted from Vagrant Cloud, a NodeSource major no longer published, an image tag removed, a pin with a known advisory — the tutorial is broken or unsafe *today* |
| **Framework (needs care)** | Moving `frappe_commit` (especially across a version or requirement change), a Python/Node floor raise, ansible-core minor/major, a new Ubuntu LTS, a MariaDB/redis series change |
| **Routine** | Box patch releases, image patch updates under the same tag, uv, yarn and frappe-bench patch/minor releases |

For each entry give **current → latest**, the file to edit, and a one-line risk note. Say
explicitly which pins are already current.

## Applying updates (only after the user picks)

1. Bump in small batches: routine pins together, then `frappe_commit` **on its own**.
2. Edit the pin(s) only in their single home (see the table above). No other file should
   hold a version.
3. Update `README.md` in the same change: the version tables (chapter 2, 3.1 or 4.1), and section 3.3 if a
   command changed. `CLAUDE.md` too if a constraint it states changed (Python/Node floors).
4. **Back up** the real stacks first (`scripts/backup.sh`, `--target vm`), then run
   **both** provisioning gates. Every pin change affects both paths:
   ```bash
   tests/gate.sh && tests/gate.sh --compose
   ```
5. After a `frappe_commit` move, also open the report in a browser
   (http://127.0.0.1:18000/desk/query-report/Daily%20HR%20Cost) and check the Employee and
   Work Record forms. The unit tests don't cover the desk UI. Remind the user that
   existing compose stacks need `podman compose down && podman compose up -d --build`
   (`docs/ops.md`, "Upgrades").
6. Commit each batch separately. For example, `build(deps): bump uv to 0.13.1, frappe-bench
   to 5.32.0`, or `build(frappe): move develop pin to <short-sha>` with the version and
   requirement changes noted in the body.
