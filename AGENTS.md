# ZingBang Workspace

This is the meta-repo entrypoint for ZingBang development. Launch `opencode` from this directory when you need workspace-level context, then `cd` into a sibling repo to do real work: each sibling (`zingbang_business`, `zingbang_foundations`, etc.) is the actual project with its own `mise` tasks and tooling.

## Repository Map

| Repo | Purpose | Key Commands |
|------|---------|--------------|
| `zingbang_platform_api` | Platform admin plane API, hosted customer/admin dashboards, and dashboard auth/session (Go + Astro) | `mise run build`, `mise run test`, `mise run db:up`, `mise run migrate:up`, `mise run dashboard:fixtures`, `mise run dashboard:storybook`, `mise run dashboard:e2e` |
| `zingbang_local_experiments` | Local federation E2E, kind/Submariner/Yugabyte | `mise run kind:create`, `mise run submariner:deploy`, `mise run ci:e2e:federation` |
| `zingbang_foundations` | Cloud infra (OpenTofu), AWS/GCP foundations | `mise run tofu:plan:dev`, `mise run tofu:apply:dev` |
| `zingbang_cluster_ops` | Cluster manifests, GitOps configs | N/A (YAML manifests) |
| `zingbang_business` | ADRs, briefs, architecture docs | N/A (Markdown) |
| `zingbang_site` | Marketing/docs site implementation | TBD |

## Terminology

- `platform admin plane`: Management/API plane at `api.<product>.<tld>` (MVP: `api.zingbang.io`)
- `customer runtime plane`: Workload/data plane at `apps.<product>.<tld>` (MVP: `apps.zingbang.io`)
- `customer app`: Hosted customer dashboard at `app.zingbang.io`
- `admin app`: Hosted internal admin dashboard at `admin.zingbang.io`

## Dashboard Surfaces

The dashboard code lives in `zingbang_platform_api`, not `zingbang_site`.

- Customer dashboard frontend bundle: `../zingbang_platform_api/customer_dashboard_web`
- Admin dashboard frontend bundle: `../zingbang_platform_api/platform_admin_web`
- Static asset serving and host-based routing: `../zingbang_platform_api/internal/api/static.go`
- Customer dashboard auth/session endpoints and cookies: `../zingbang_platform_api/internal/api/auth_tokens.go`
- Shared API routing for hosted dashboard-backed endpoints: `../zingbang_platform_api/internal/api/server.go`

Use `zingbang_site` for marketing/docs content and public-site UX. Use `zingbang_platform_api` for hosted dashboard work, dashboard auth/session, and customer/admin API behaviors that back those surfaces.

### Frontend UX Workflow

- For admin dashboard UX work, prefer the deterministic frontend tooling in `../zingbang_platform_api` before jumping straight into live API mode.
- Use `mise run dashboard:fixtures` for routed fixture-state review at `http://127.0.0.1:4321/fixtures`.
- Use `mise run dashboard:storybook` for isolated admin state inspection backed by the same fixture scenarios.
- Use `mise run dashboard:e2e` for browser-driven operator flow validation.
- Use `mise run dashboard:visual:update` only when a visual regression baseline change is intentional and reviewed.
- For non-trivial frontend changes, inspect the relevant fixture state first, then validate behavior with Playwright.

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
- Frontend UX work: run the relevant dashboard checks (`dashboard:check`, `dashboard:e2e`, and fixture/storybook review as appropriate).
- Full federation E2E is not required pre-commit, but changes must be locally sanity checked to avoid CI-only debugging.

### Plane Integration
- Plane is source of truth for task state
- Active project model:
  - `Platform Milestones` for cross-repo milestones and delivery outcomes
  - `Platform API`, `Foundations`, `Cluster Ops`, `Local Experiments`, and `Site` for repo-aligned execution
  - `Go-To-Market` for market, customer, and business execution
  - `Legacy - Platform Delivery` is frozen legacy history; do not create new tickets there
- Label conventions (lightweight): keep `type:*` and `horizon:*`; add `milestone` only when it improves filtering; avoid `track:*` and `component:*` on new tickets
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
- Cross-repo delivery outcomes in `Platform Milestones`
- Substrate foundations and GitOps split between `Foundations` and `Cluster Ops`
- Platform product/control-plane work in `Platform API`

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
