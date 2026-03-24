# ZingBang Workspace

This is the meta-repo entrypoint for ZingBang development. Launch `opencode` from this directory when you need workspace-level context, then `cd` into a sibling repo to do real work: each sibling (`zingbang_business`, `zingbang_foundations`, etc.) is the actual project with its own `mise` tasks and tooling.

## Repository Map

| Repo | Purpose | Key Commands |
|------|---------|--------------|
| `zingbang_platform_api` | Platform admin plane API (Go) | `mise run build`, `mise run test`, `mise run db:up`, `mise run migrate:up` |
| `zingbang_local_experiments` | Local federation E2E, kind/Submariner/Yugabyte | `mise run kind:create`, `mise run submariner:deploy`, `mise run ci:e2e:federation` |
| `zingbang_foundations` | Cloud infra (OpenTofu), AWS/GCP foundations | `mise run tofu:plan:dev`, `mise run tofu:apply:dev` |
| `zingbang_cluster_ops` | Cluster manifests, GitOps configs | N/A (YAML manifests) |
| `zingbang_business` | ADRs, briefs, architecture docs | N/A (Markdown) |
| `zingbang_site` | Product/site implementation | TBD |

## Terminology

- `platform admin plane`: Management/API plane at `api.<product>.<tld>` (MVP: `api.zingbang.io`)
- `customer runtime plane`: Workload/data plane at `apps.<product>.<tld>` (MVP: `apps.zingbang.io`)

## Cross-Repo Workflows

### Platform API → Cluster Ops Promotion
1. Merge to `main` in `zingbang_platform_api`
2. `release-and-promote.yml` builds ARM64 image, pushes to GHCR
3. Creates PR in `zingbang_cluster_ops` with updated image tag
4. Merge cluster-ops PR to deploy to dev clusters

### Local Federation E2E
1. `zingbang_local_experiments` CI pulls `ghcr.io/kismet-engineering/zingbang-platform-api:dev`
2. Creates kind clusters (aws, gcp) with Submariner mesh
3. Deploys Yugabyte, runs platform-api migrations
4. Executes federation lifecycle tests

### Infra Changes
1. Edit OpenTofu in `zingbang_foundations`
2. Run `mise run tofu:plan:dev` to validate
3. Apply changes, export outputs
4. Update downstream consumers if output shapes change

See `docs/getting-started.md` for the high-level delivery flow and the current owner responsibilities between the repos.

## Shared Conventions

### Commit Style
- Short, imperative subjects ("Add compose scaffold", "Fix image arch mismatch")
- Reference Plane issue ID in commits and PRs
- Group related changes by concern

### Pre-Commit Verification

Run local verification for changes that can be validated in under ~5 minutes.

- Infra/manifests: validate + smoke test locally (example: Yugabyte changes require `mise run yb:k8s-up` and `mise run yb:k8s-smoke`).
- Scripts: run the script locally and shellcheck when possible.
- Application code: run the relevant unit tests and lint/typecheck tasks when available.
- Full federation E2E is not required pre-commit, but changes must be locally sanity checked to avoid CI-only debugging.

### Plane Integration
- Plane is source of truth for task state
- Prefer projects: `Platform Delivery` or `Go-To-Market`
- Label conventions (lightweight): one `track:*`, one `type:*`, one `horizon:*`, one `component:*`
- Update issue with file paths and validation notes after implementation
- Always close tickets with a comment that links to the work (commit/PR) and summarizes evidence delivered
- Project/ticket updates should use short bullet lists (avoid paragraph walls of text)

### Code Style
- Go: tight package boundaries (`api` for transport, `service` for domain)
- YAML: 2-space indentation
- Markdown: concise headings, bullet lists
- Keep files ASCII unless existing content requires otherwise

### Security
- Never commit secrets or `.env` files
- Use `local/.env` for local-only secrets (gitignored)
- Rotate credentials when sharing compose files

### GitOps Discipline
- Avoid "monkey patching" shared clusters with ad-hoc `kubectl apply`, `helm install`, or `terraform apply` invocations. Land declarative changes in the owning repo (or the appropriate `mise` automation) and let Flux/CI reconcile them.
- If a break-glass live edit is unavoidable, record the exact commands in the Plane issue and follow up immediately with a GitOps change that makes the fix repeatable before leaving the cluster in that state.

## Active Plane Context

Current focus areas (update as priorities shift):
- Federation E2E CI in Platform Delivery
- Substrate foundations: AWS, GCP, federation contract
- Platform API features: tracked in Platform Delivery project

## Environment Setup

### Prerequisites
- `mise` for per-repo task running (run `mise` only inside the repo whose `.mise.toml` you need)
- `podman` or `docker` for containers
- `kubectl`, `kind`, `subctl` for k8s/federation work

### Quick Start
```bash
cd ~/dev/zingbang/zingbang_workspace
opencode  # Launches with full project context
cd zingbang_business  # move into a real repo before running mise or other repo-specific commands
```

### Release/Automation Notes
- Always run `mise run <task>` inside the repo that owns the `.mise.toml` defining `<task>` (e.g., release notes live in `zingbang_business`). `mise` run from the workspace root will report "no tasks defined" because the workspace itself is just an entrypoint.
- All release artifacts (manifests, changelog entries, release notes) belong in `zingbang_business/docs/releases/`. Do not add or edit release docs from the workspace root.
- Credentials for release automation (Plane API key, AWS/GCP roles, email service tokens) come through environment; do not hardcode secrets in files. See `scripts/` directories in other repos for CLI helpers.

## Related Documentation

- `../zingbang_business/docs/adrs/` - Architecture Decision Records
- `../zingbang_business/docs/roadmap/` - Roadmap docs
- `../zingbang_platform_api/docs/design-freeze-v0.md` - API design freeze
- `../zingbang_platform_api/docs/api/` - OpenAPI specs
