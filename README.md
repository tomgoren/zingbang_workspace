# ZingBang Workspace

Meta-repo entrypoint for cross-repo ZingBang development. Launch opencode from this directory to work across all ZingBang repos with full project context.

## Quick Start

```bash
cd ~/dev/zingbang/zingbang_workspace
opencode
```

## Repository Overview

| Repo | Description |
|------|-------------|
| [zingbang_platform_api](../zingbang_platform_api) | Platform admin plane API, hosted customer/admin dashboards, and dashboard auth/session (Go + Astro) |
| [zingbang_local_experiments](../zingbang_local_experiments) | Local federation E2E, kind/Submariner |
| [zingbang_foundations](../zingbang_foundations) | Cloud infra (OpenTofu) |
| [zingbang_cluster_ops](../zingbang_cluster_ops) | Cluster manifests, GitOps |
| [zingbang_business](../zingbang_business) | ADRs, briefs, docs |
| [zingbang_site](../zingbang_site) | Marketing/docs site only |

## Documentation

See [AGENTS.md](./AGENTS.md) for full context including conventions, workflows, and commands.

## Dashboard Architecture

- `zingbang_site` owns the public marketing/docs experience at `zingbang.io`; it does not contain the hosted product dashboards.
- `zingbang_platform_api` owns the hosted product surfaces and the public API:
  - customer app: `app.zingbang.io`
  - internal admin app: `admin.zingbang.io`
  - public API: `api.zingbang.io`
- The dashboard frontend bundles live in the platform API repo:
  - customer dashboard: `../zingbang_platform_api/customer_dashboard_web`
  - admin dashboard: `../zingbang_platform_api/platform_admin_web`
- The Go service in `../zingbang_platform_api/internal/api` serves those built frontend assets, applies host-based routing, and handles hosted auth/session flows.
- Work in `zingbang_site` when the change is marketing/docs/navigation/content; work in `zingbang_platform_api` when the change affects the customer dashboard, admin dashboard, dashboard auth/session, or dashboard-backed API behavior.

## Plane project model

- `Platform Milestones` owns cross-repo milestones and delivery outcomes.
- `Platform API`, `Foundations`, `Cluster Ops`, `Local Experiments`, and `Site` own repo-aligned execution.
- `Go-To-Market` owns market/customer/business execution.
- `Legacy - Platform Delivery` is legacy history only.
