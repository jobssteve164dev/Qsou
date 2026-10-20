# Dependency security maintenance

## 2026-10-20 remediation

GitHub's live Dependabot API confirmed alerts 402–424 were open against
`37b70094cf9661148b4c1e7244ff6c8f2a98a062`. Duplicate alerts refer to the same
advisory in multiple manifests, rather than separate application defects.

| Alerts | Dependency and actual consumer | Remediation |
| --- | --- | --- |
| 402, 403, 419, 420 | Next.js server, pages and same-origin API proxy | Next.js and eslint-config-next 16.3.8 |
| 404–415 | pypdf in crawler source adapters, normal collection and evidence replay | Both crawler requirements files pin 6.21.1 |
| 416–418, 422 | brace-expansion through minimatch/glob and ESLint | Lock 1.1.21, 2.1.7 and 5.0.12 on their existing major branches |
| 421 | source-map-js through PostCSS | Lock 1.2.2 |
| 423 | braces through micromatch and chokidar, consumed by Tailwind and Next.js linting | Exact npm alias to @dieub/braces-depth-guard 3.0.3-pn.3 |
| 424 | postcss-selector-parser through Tailwind, postcss-nested and typography | Override all copies to 7.1.6 |

The same audit also found vulnerable sharp 0.35.4, so the existing Next.js image
dependency is overridden to 0.35.5 with its matching native packages.
The legacy API requirements also pinned aiohttp 3.14.3; 3.14.4 fixes two high
severity advisories and one low severity cookie advisory. Current repository
code consumes aiohttp indirectly through AsyncElasticsearch's AiohttpHttpNode
transport when Elasticsearch is enabled. `dev.sh` installs the legacy API
requirements; production uses a separate API requirements file whose audited
graph already resolves the patched transport. Both installation paths must
resolve a patched version.

### Temporary braces override

[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
has no patched upstream release as of this audit. The scoped
[depth-guard backport](https://github.com/dieub/braces-depth-guard) preserves
the braces 3 API and avoids a Tailwind major-version migration. The published
tarball was compared with braces 3.0.3: the entrypoint and license are unchanged;
runtime differences add nesting limits, validate limit options and reject AST
parent cycles. It adds no runtime dependency or installation lifecycle script.
The exact version and tarball integrity are pinned by the npm lockfile.

Keep the override until upstream publishes a verified compatible fix. Do not
replace it with an unbounded semver range or merely remove the override to
silence a scanner. The regression suite resolves braces from both actual
consumers, checks normal source globs and rejects deep strings and prebuilt ASTs.

The pypdf update includes the six listed advisories and subsequent security
patches through 6.21.1. Tests exercise real announcement text extraction and
malformed alphabetical page labels through PdfReader. The old versions fail the
security assertions; the patched versions pass.

### Verification and release boundary

Run the repository CI gates, including `npm ci`, `npm run test:security`,
`npm run lint`, `npm run build`, Alembic and `python -m pytest tests -q` against
an isolated PostgreSQL database. Audit all seven Python requirements graphs and
the installed npm graph. Exercise the built web server through a real browser
before releasing the web service; verify the final amd64 image through the
existing cross-architecture CI job.

Do not equate a clean dependency manifest with a deployed fix or a closed GitHub
alert. The explicit collector command preserves its image default and makes the
final Compose process identity visible to release preflight. A root Compose
change releases the entire project through the existing build chain. Register
the collector and indexer process criteria through the governed service contract
before triggering production; do not add worker HTTP ports for this purpose.

### Twisted upstream fix and release follow-up

Twisted has not published a patched PyPI release for its
[IMAP advisory](https://github.com/advisories/GHSA-8pqf-f4m5-798g), but the
[upstream fix](https://github.com/twisted/twisted/commit/2f8a3c29246f4eb324690e06a9767a11dc4aec9f)
is available. All three Scrapy installation paths pin that exact source archive
and its SHA-256. Its upstream version is 26.4.0.post0. Regression tests prove
mailbox text cannot become regex syntax while preserving IMAP wildcard rules.

Audits retain pip-audit's PyPI service for published releases. For a release
absent from PyPI, the audit queries OSV with the resolver's actual package name
and version. Every resolved dependency must be audited; unresolved dependencies,
service failures and findings from either source fail the job. No advisory is
ignored and no feature is disabled. This keeps the existing advisory source
while covering the official Twisted post-release source build. OSV's older
PYSEC-2017-83 record has an open-ended Scrapy range; the reviewed
[GitHub advisory](https://github.com/advisories/GHSA-h7wm-ph43-c39p) bounds it at
2.15.2. The existing PyPI source reports no finding for the installed 2.19.0.
Return to a compatible official wheel after a patched release and the same
regressions have been verified.

The release prerequisite adds an optional expected main-process identity to
the existing GitOps service and frozen release contract. It compares the
registered command with the inspected running container, using the existing
Compose preflight, release producer and signed Agent upgrade. HTTP contracts
and existing services without the new criterion keep their accepted behavior.
Register the collector and indexer only after the target Agent supports the new
contract, then publish the tested Qsou candidate through its existing release
path and read back the exact service versions and public product entry.
