---
name: release-engineering
description: Cut a versioned release of this Frappe onboarding project — a tested, tagged snapshot of the tutorial (Vagrant VM and podman compose paths) with its exact pins (box, container images, ansible-core, frappe commit, …) — including semver choice, all gates, CHANGELOG entry, annotated tag, and GitHub release.
---

A release here is **a tutorial snapshot that is known to build**. Learners should be able to
`git checkout vX.Y.Z && vagrant up` (or `podman compose up -d --build`) months later and get
exactly what the docs describe.
That's why each release records its pins, and the full gate must pass on the tagged commit.

The version lives in **two places, kept equal**: the git tag `vX.Y.Z` and the top entry of
`CHANGELOG.md`. The app's own `apps/hr_cost/hr_cost/__init__.py` `__version__` moves only
when the app itself changed.

Steps:

1. **Determine the release type.** Review every commit since the last tag
   (`git log $(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline`, or all commits
   if there's no tag yet) and classify it by [SemVer](https://semver.org/), as it affects a
   **learner following the tutorial**:
   - **major**: the tutorial's path changes in a way that invalidates old instructions. For
     example: a new Frappe major (17 → 18), a new Ubuntu LTS, a changed default URL, site
     name or credentials, removed or renamed app DocTypes or fields, or a compose volume
     layout change that makes existing volumes unusable (which needs a documented
     backup → restore migration).
   - **minor**: new capability or content, such as a new report or field, a new tutorial
     section, a new role, or a `frappe_commit` move within the same major.
   - **patch**: fixes and routine pin bumps (uv, yarn, bench patch, box patch), and doc
     corrections.

   Present the recommendation and **confirm with the user** before continuing.

2. **Run every gate** and don't continue if anything fails:
   ```bash
   tests/gate.sh && tests/gate.sh --compose
   ```
   `--compose` includes the persistence and backup → restore round trip. Also dry-run the
   timer (`scripts/install-backup-timer.sh`). Never enable it.
   A release also needs a real **VirtualBox** run (`vagrant destroy -f && vagrant up`) on a
   host that has VirtualBox. The container gate doesn't exercise vboxsf, NAT port forwarding
   or the box itself. If that isn't possible here, say so explicitly and let the user decide
   whether to tag anyway. Don't claim a VirtualBox verification that didn't happen.

3. **Run the `docs-engineering` skill.** The README's version tables (chapter 2, 3.1, 4.1) and section 3.3
   must match the pins being released.

4. **Update `CHANGELOG.md`.** Add the new version at the top in
   [Keep a Changelog](https://keepachangelog.com/) format: `Added` / `Changed` / `Fixed` /
   `Removed` / `Security`. Every entry includes a **"Pinned versions"** block copied from the
   current pins: box, container images (ubuntu, mariadb, redis), ansible-core, uv, Python,
   Node, yarn, frappe-bench, and the frappe commit with its `__version__`. Call out any
   change that needs an action from existing users, such as rebuilding the compose image
   or restoring into a new volume layout. If `CHANGELOG.md` doesn't exist yet, create it with an
   `## [Unreleased]` section and this release as the first versioned entry.

5. **Commit the release** (`CHANGELOG.md`, plus the app `__version__` if bumped):
   `chore: release vX.Y.Z`.

6. **Tag it.** Create an annotated tag, `git tag -a vX.Y.Z -m "vX.Y.Z"`, and report the full
   commit SHA it names (`git rev-parse vX.Y.Z^{commit}`). If a remote exists, push the commit
   and the tag (`git push && git push --tags`). If `git remote` is empty, stop here and tell
   the user a remote is needed for publishing.

7. **Create a GitHub release** when a GitHub remote is configured:
   `gh release create vX.Y.Z --title vX.Y.Z --notes-file <the CHANGELOG section>`. Note in
   the release body whether the VirtualBox run from step 2 happened.
