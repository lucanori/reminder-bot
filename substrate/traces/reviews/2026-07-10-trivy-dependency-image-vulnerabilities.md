---
status: completed
created_at: 2026-07-10
updated_at: 2026-07-11
reviewer: security-review-specialist
target: reminder-bot dependency tree (fs scan) and python:3.14.3 base image (image scan)
scope: >
  Read-only triage of supplied Trivy results: 2 HIGH findings from fs scan on
  Mako 1.3.10; 972 HIGH/CRITICAL findings from image scan on python:3.14.3
  Debian (321 without fix, 651 with fix). No active pentest, no Docker run, no
  file edits outside substrate/traces/reviews/.
supporting_docs:
  - Dockerfile
  - pyproject.toml
  - uv.lock (not read; version inferred from pyproject.toml constraints)
---

# Trivy dependency and image vulnerability triage

## Summary

Two HIGH CVEs in Mako 1.3.10 are real, fixable by upgrading to Mako >=1.3.12,
and have low exploitability in this application. The 972 image-level
HIGH/CRITICAL findings split into 651 addressable by base-image change and 321
structurally unfixable today. The unfixable 321 are Debian bookworm OS-package
CVEs with no upstream patch; they cannot be zeroed without switching distro or
accepting residual risk. Zero secrets found. No critical application-layer CVE
was identified.

## Scope and methodology

Source-only review. Trivy results supplied by the requesting agent; not
independently executed. Dockerfile and pyproject.toml read to confirm base
image, dependency constraints, and runtime context. CVE details verified via
NVD, GitHub Advisory Database, and Debian Security Tracker. No Docker, network,
active, or exploit tests were run.

## Findings by severity

### High

#### 🔴 bug: Mako 1.3.10 path traversal via double-slash URI (CVE-2026-41205)

- **Location:** `pyproject.toml` dependency `mako` (transitive via `alembic`); Mako <=1.3.10
- **Evidence:** `TemplateLookup.get_template()` strips all leading `/` with `re.sub`; `Template.__init__` strips only one. URI `//../../../../etc/passwd` bypasses the `startswith("..")` traversal check. CVSS v4 7.7 HIGH. Fixed in Mako 1.3.11 (commit `e05ac61`).
- **Impact:** Any file readable by the process can be returned as rendered template content when untrusted input reaches `TemplateLookup.get_template()`. Alembic uses Mako for migration templates; template URIs are not user-controlled in this bot. Exploitability is therefore low in practice.
- **False-positive notes:** HTTP exploitation is mitigated by CPython's `BaseHTTPRequestHandler` normalizing double-slash prefixes (gh-87389). Flask is used here, not `BaseHTTPRequestHandler`, so the mitigation does not apply at the framework level. However, no code path in this bot passes untrusted user input to `TemplateLookup.get_template()`. Risk is real but requires a code-path change to become exploitable.
- **Remediation:** Upgrade Mako to >=1.3.12 (covers both CVE-2026-41205 and CVE-2026-44307). In `pyproject.toml` Mako is a transitive dep of `alembic`; pin `mako>=1.3.12` explicitly or wait for alembic to pull it transitively. Run `uv lock --upgrade-package mako` and rebuild.

#### 🔴 bug: Mako 1.3.10 path traversal via backslash URI on Windows (CVE-2026-44307)

- **Location:** `pyproject.toml` dependency `mako` (transitive via `alembic`); Mako <1.3.12
- **Evidence:** Backslash traversal `\..\..\ secret.txt` bypasses `Template.__init__` check and `posixpath`-based normalization in `TemplateLookup.get_template()`. CVSS v4 8.7 HIGH. Fixed in Mako 1.3.12 (commit `72e10c5`).
- **Impact:** Arbitrary file read outside template directory. Windows-specific; container runs Linux. Exploitability is effectively zero in this deployment.
- **False-positive notes:** Container OS is Linux (Debian). `posixpath` does not treat backslash as separator. This CVE is a true positive at the library level but a false positive for this Linux container deployment. Still worth patching to keep the dependency clean.
- **Remediation:** Same as CVE-2026-41205: upgrade Mako to >=1.3.12.

### High (image-level, with fix available)

#### 🟡 risk: 651 HIGH/CRITICAL Debian OS-package CVEs with upstream fixes available

- **Location:** `FROM python:3.14.3` in `Dockerfile:3`; Debian bookworm base layer
- **Evidence:** Trivy image scan reports 651 HIGH/CRITICAL findings with a fixed version available. These are Debian OS packages (glibc, openssl, curl, libxml2, and similar) where upstream has released a patch but the `python:3.14.3` image has not yet incorporated it, or where a newer Debian release (trixie/sid) carries the fix.
- **Impact:** Exploitability depends on whether the vulnerable package is reachable from the network or from untrusted input. Many OS-level CVEs in a bot container have no direct attack surface (e.g., curl CVEs when curl is not called at runtime). However, some (openssl, glibc) can affect TLS and memory safety in the Python runtime itself.
- **False-positive notes:** Trivy reports source-package CVEs that may not affect the installed binary package (known Debian tracker issue: `<ignored>` and `<no-dsa>` states are sometimes not propagated to Trivy). A significant fraction of the 651 may be informational noise. Actual exploitable count is lower; exact number requires per-CVE triage with `--ignore-unfixed` and Debian tracker cross-reference.
- **Remediation (priority order):**
  1. Switch to `python:3.14.3-slim` — removes ~400-500 MB of non-runtime packages (gcc, binutils, perl, and similar), eliminating a large share of the 651 fixable CVEs that exist only in dev/build tooling not needed at runtime. The Dockerfile already uses `uv sync --no-dev`, so the slim variant is compatible.
  2. Use multi-stage build — build stage uses `python:3.14.3` (or `python:3.14.3-slim`), final stage copies only `.venv` and app code into `python:3.14.3-slim` or `gcr.io/distroless/python3`. Eliminates build toolchain from the runtime image entirely.
  3. Pin to a newer image digest weekly via Dependabot or Renovate — ensures Debian security updates are pulled as they land in the official image.
  4. Consider `python:3.14.3-slim-bookworm` or wait for `python:3.14.3-slim-trixie` — trixie carries more upstream fixes than bookworm for several packages.

### High (image-level, no fix available)

#### 🟡 risk: 321 HIGH/CRITICAL Debian OS-package CVEs without any upstream fix

- **Location:** `FROM python:3.14.3` in `Dockerfile:3`; Debian bookworm base layer
- **Evidence:** Trivy image scan reports 321 HIGH/CRITICAL findings with no fixed version. These are CVEs where Debian has not yet backported a patch, upstream has not released a fix, or Debian has marked the issue `<no-dsa>` (not severe enough for a Debian Security Advisory) or `<postponed>`.
- **Impact:** Cannot be eliminated by any base-image upgrade within the Debian ecosystem today. Switching to Alpine or distroless reduces the OS package surface and may remove some of these, but Alpine uses musl libc and may introduce compatibility issues with asyncpg and other C-extension packages.
- **False-positive notes:** A substantial portion of the 321 are likely `<no-dsa>` or `<ignored>` in the Debian tracker, meaning Debian's own security team assessed them as low-priority or not affecting the binary package. Trivy does not always filter these. True exploitable count is likely well below 321. This is the primary source of false positives in the scan.
- **Remediation:** These cannot be zeroed. Acceptable risk criteria apply (see below). Use `trivy image --ignore-unfixed` to separate this bucket from the fixable 651 in CI reporting. Document accepted residual risk in a `.trivyignore` or VEX file with justification per CVE family.

## Elimination analysis

| Bucket | Count | Elimination path | Realistic? |
|---|---|---|---|
| Mako CVE-2026-41205 | 1 HIGH | `uv lock --upgrade-package mako` to >=1.3.11 | Yes, immediate |
| Mako CVE-2026-44307 | 1 HIGH | `uv lock --upgrade-package mako` to >=1.3.12 | Yes, immediate |
| Image CVEs with fix | ~651 | Switch to `python:3.14.3-slim` + multi-stage build | Yes, large reduction; not zero |
| Image CVEs no fix | ~321 | Cannot be eliminated; distroless reduces surface | No, accept with criteria |

Switching to slim alone typically removes 60-80% of OS-package CVEs. Multi-stage
distroless removes another 10-15%. The residual unfixable set shrinks but does
not reach zero on any Debian-based image.

## Measurable acceptance criteria

These criteria define when the image posture is acceptable for production:

1. **Zero HIGH/CRITICAL with fix in application layer** — `trivy fs . --severity HIGH,CRITICAL` reports zero findings after Mako upgrade.
2. **Image fixable CVEs below 50** — `trivy image --ignore-unfixed --severity HIGH,CRITICAL` reports fewer than 50 findings after slim/multi-stage migration. This is achievable; it filters the 321 no-fix bucket and targets the residual fixable set after slim migration.
3. **No CRITICAL CVEs with fix in runtime packages** — zero CRITICAL findings with a fixed version in packages actually present in the final runtime image (not build-stage only).
4. **Weekly image rebuild** — CI rebuilds and rescans the image weekly; any new fixable HIGH/CRITICAL blocks merge within 7 days.
5. **VEX/trivyignore for accepted no-fix CVEs** — each accepted no-fix CVE has a documented justification entry. Entries are reviewed quarterly.

## False-positive risk summary

- **CVE-2026-44307 (Mako backslash):** True positive at library level, false positive for this Linux container. Patch anyway.
- **Debian `<no-dsa>` / `<ignored>` CVEs:** Trivy does not filter these by default. A significant share of the 321 no-fix findings and some of the 651 fixable findings may be Debian-assessed as non-critical for the binary package. Cross-reference each HIGH/CRITICAL with `https://security-tracker.debian.org/tracker/<CVE>` before escalating.
- **Build-toolchain CVEs in non-slim image:** gcc, binutils, perl, and similar packages present in `python:3.14.3` but absent in `python:3.14.3-slim` generate real CVEs that have zero runtime attack surface. Slim migration eliminates these without any VEX entry needed.
- **Source-vs-binary package mismatch:** Debian tracks CVEs at source-package level. A CVE in a source package may not affect the binary package installed in the image. Trivy sometimes reports these; the Debian tracker `<not-affected>` state is the authoritative signal.

## Remediation timeline

1. **Immediate (before next merge):** Upgrade Mako to >=1.3.12 via `uv lock --upgrade-package mako`. Eliminates both fs-scan HIGH findings.
2. **Short-term (within 1 sprint):** Switch `FROM python:3.14.3` to `FROM python:3.14.3-slim` and add multi-stage build. Eliminates the majority of the 651 fixable image CVEs.
3. **Short-term (same sprint):** Add `trivy image --ignore-unfixed --severity HIGH,CRITICAL --exit-code 1` to CI with the slim image. Gate merges on zero fixable HIGH/CRITICAL.
4. **Medium-term (within 1 month):** Triage the residual no-fix 321 against the Debian tracker. Create `.trivyignore` or VEX entries for confirmed `<no-dsa>` / `<ignored>` findings. Document accepted risk.
5. **Ongoing:** Weekly image rebuild via Renovate/Dependabot digest pinning. Quarterly review of VEX entries.

## Validation notes

- After Mako upgrade: `trivy fs . --severity HIGH,CRITICAL` must report zero findings.
- After slim migration: `trivy image --ignore-unfixed --severity HIGH,CRITICAL reminder-bot:latest` must report fewer than 50 findings.
- After CI gate: a PR that introduces a new HIGH/CRITICAL fixable CVE must fail the pipeline.
- Debian tracker cross-reference: for each remaining no-fix finding, confirm status at `https://security-tracker.debian.org/tracker/<CVE-ID>` before adding to VEX.

## Update: 2026-07-11 by security-review-specialist

### Prior finding status

- Mako path traversal CVE-2026-41205 (high): resolved. `pyproject.toml:11` now requires Mako >=1.3.12, and `uv.lock:461-469` resolves Mako 1.3.12 with artifact hashes.
- Mako path traversal CVE-2026-44307 (high): resolved by same Mako 1.3.12 floor and lock entry.
- Fixable Debian application-image findings (high): resolved for application runtime. `Dockerfile:3`, `Dockerfile:20`, and `Dockerfile:28` replace single-stage Debian runtime with multi-stage `python:3.14.5-alpine3.23`; supplied final Trivy result reports zero OS findings.
- Unfixed Debian application-image findings (high): eliminated from application runtime by same Alpine migration. This is surface removal, not upstream patching.

### Verdict

Application remediation passes source review. No introduced critical, high, or medium vulnerability found. One low supply-chain pinning risk remains. Whole-stack zero-vulnerability claim does not pass: unchanged PostgreSQL image retains one high residual finding group. Final application-image zero claim remains supplied, not independently reproduced.

### New findings

#### High

##### 🟡 risk: Unchanged PostgreSQL image retains critical and high scanner findings

- **Location:** `docker-compose.yml:37`; `docker-compose.local.yml:37`
- **Status:** Pre-existing and not introduced by remediation.
- **Evidence:** Both Compose files retain `postgres:18`. Supplied `/tmp/opencode/reminder-bot-postgres18.json` records 329 vulnerability occurrences: 9 critical, 48 high, 109 medium, 131 low, and 32 unknown. Debian packages account for 290 findings without fixes. `gosu` accounts for 39 findings with fixes. Repeated Perl package records inflate occurrence count, but do not remove underlying CVEs.
- **Impact:** Compromise of reachable vulnerable PostgreSQL startup or runtime code could expose or alter reminder data. Compose publishes no PostgreSQL host port, so exploitation requires application compromise, another container on Compose network, or a vulnerable path reachable through database traffic. `gosu` runs during container privilege transition, reducing exposure after startup.
- **False-positive notes:** Scanner severity does not prove reachability. Most Debian findings have no fixed version, and several critical occurrences duplicate same CVEs across related Perl packages. Private-key match at `/etc/ssl/private/ssl-cert-snakeoil.key` is Debian snakeoil material, not application credential; PostgreSQL config shown here does not select it, so treat secret alert as false positive. No secret content was read or copied. Alpine replacement was correctly deferred because moving existing PostgreSQL data from glibc to musl in place risks locale and collation incompatibility.
- **Remediation:** Keep database network-isolated. Rebuild and rescan newest Debian `postgres:18` digest. Replace vulnerable `gosu` build when upstream image updates. Plan staged Alpine migration with backup, dump/restore into new volume, collation-dependent index rebuild, integrity checks, and rollback. Do not mount existing Debian-initialized volume directly into Alpine image.

#### Low

##### 🟡 risk: Executable build and deployment images remain tag-pinned, not digest-pinned

- **Location:** `Dockerfile:3`, `Dockerfile:12`, `Dockerfile:20`; `docker-compose.yml:3`, `docker-compose.yml:7`, `docker-compose.yml:37`; `docker-compose.local.yml:37`
- **Status:** Partly introduced. New external `uv` build stage adds unpinned executable source. Python, application `latest`, and PostgreSQL tag mutability predate remediation.
- **Evidence:** Build trusts mutable tags `python:3.14.5-alpine3.23` and `ghcr.io/astral-sh/uv:0.11.28`. Production always pulls mutable `ghcr.io/lucanori/reminder-bot:latest`. Compose database uses mutable `postgres:18`. `uv.lock:1-7` and package entries such as `uv.lock:461-469` provide package version and hash integrity, but do not authenticate container tag contents.
- **Impact:** Registry or publisher compromise, or accidental tag retargeting, can change build tool, base runtime, application artifact, or database image without repository diff. Malicious `uv` can poison installed runtime code during build.
- **False-positive notes:** Versioned tags constrain normal upgrades, registries use authenticated TLS, and lock hashes protect Python downloads. Risk concerns tag mutability and publisher trust, not current image content. `apk upgrade` at `Dockerfile:22-24` also makes package patch level build-time dependent, but improves vulnerability freshness.
- **Remediation:** Pin Python, `uv`, application release, and PostgreSQL images by OCI digest. Keep readable tag plus digest. Use Renovate or Dependabot to submit reviewed digest updates and rebuild on security cadence.

### New validation notes

- `uv lock --check` passed during this review. Lock resolves 54 packages and includes hashes. Mako 1.3.12 is fixed at `uv.lock:461-469`; key updated packages appear at `uv.lock:574-590`, `uv.lock:691-692`, `uv.lock:803-812`, `uv.lock:830-833`, `uv.lock:864-871`, and `uv.lock:1096-1097`.
- Alpine/musl compatibility has source support: asyncpg provides CPython 3.14 musllinux wheels at `uv.lock:100-101`; Pydantic core provides CPython 3.14 musllinux wheels at `uv.lock:651-668`; MarkupSafe provides CPython 3.14 musllinux wheels at `uv.lock:527-529`. Supplied runtime import and 248-test results support compatibility, but were not rerun here.
- Pip removal is explicit at `Dockerfile:22-24`; `uv` stays builder-only at `Dockerfile:12`, and runtime copy at `Dockerfile:28` does not copy `/usr/local/bin/uv`. Supplied runtime checks report `pip`, `uv`, and `bash` absent.
- Health checks use fixed localhost URL and standard-library `urllib` at `Dockerfile:36-37`, `docker-compose.yml:29-34`, and `docker-compose.local.yml:29-34`. No user-controlled URL or shell interpolation exists.
- Runtime defaults to `nobody:nobody` at `Dockerfile:32`. Production overrides user with `${PUID}:${PGID}` at `docker-compose.yml:5`, so non-root status depends on deployment values. Local Compose remains explicitly root at `docker-compose.local.yml:5`; both overrides predate remediation.
- Archived `/tmp/opencode/reminder-bot-vuln-remediated.json` still records intermediate pip CVE-2026-8643, while supplied report says later rescan was zero after pip removal. Source supports removal, but archived artifact does not independently prove final zero. Preserve final post-removal Trivy JSON or attestation for auditable gate evidence.
- Review limits: source, diff, lock, and supplied JSON artifacts only. No Docker, Trivy execution, network, application, scanner, or active security tests were run. `git diff --check` passed. Supplied build, Compose, test, Ruff, runtime, and final scan results were considered but not independently executed.

## Update: 2026-07-11 final gate by security-review-specialist

### Prior finding status

- Executable build-image tag pinning (low, introduced portion): resolved. Builder and runtime use same immutable Python digest at `Dockerfile:3` and `Dockerfile:20`. Builder-only `uv` executable uses immutable digest at `Dockerfile:12`. Tag retargeting can no longer change these three inputs without Dockerfile diff.
- Deployment-image tag pinning (low, pre-existing portion): unresolved and not attributed to remediation. `docker-compose.yml:3` retains application `latest` with continuous pull at `docker-compose.yml:7`; `docker-compose.yml:37` and `docker-compose.local.yml:37` retain `postgres:18`. Repository has no digest-update automation. Continuous pulls provide operational patch uptake but do not provide content immutability.
- PostgreSQL critical and high scanner findings (high): unresolved, pre-existing whole-stack risk. Database image and migration constraints are unchanged. This does not affect application-image zero result.
- Final application scan evidence gap (informational): resolved. `/tmp/opencode/reminder-bot-vuln-remediated-final.json` records zero vulnerabilities and zero secrets for both Alpine OS and Python package targets. Intermediate pip finding is absent.

### New findings

No new remediation-introduced vulnerability found.

### Verdict

Pass for application dependency and container remediation. Application image and locked dependency tree have supported zero-vulnerability results across all severities. No introduced critical, high, medium, or low finding remains. Whole stack is not vulnerability-free because unchanged PostgreSQL finding remains open and requires separate risk acceptance or staged migration.

### New validation notes

- `Dockerfile:3`, `Dockerfile:12`, and `Dockerfile:20` use tag-plus-digest references. Digests, not mutable tags, select build content.
- Parsed `/tmp/opencode/reminder-bot-vuln-remediated-final.json`: Alpine OS target zero vulnerabilities and zero secrets; Python target zero vulnerabilities and zero secrets.
- Parsed `/tmp/opencode/reminder-bot-fs-final.json`: `uv.lock` target zero vulnerabilities; `Dockerfile` target zero misconfigurations; aggregate zero vulnerabilities, zero secrets, and zero misconfigurations.
- `uv lock --check` passed with 54 resolved packages. `git diff --check` passed.
- Source still confirms frozen production install at `Dockerfile:14-16`, builder-only `uv` at `Dockerfile:12`, pip removal at `Dockerfile:22-24`, non-root default at `Dockerfile:32`, and fixed-localhost health check at `Dockerfile:36-37`.
- Supplied build, runtime identity, absence of `uv` and pip, 248-test, lint, format, and Compose results support final compatibility. They were not rerun here.
- Review limits: source, cumulative diff, lock consistency, and archived JSON parsing only. No Docker, Trivy execution, network, application, or active security tests were run.
