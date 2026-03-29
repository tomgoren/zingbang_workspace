# ZingBang Workspace: Getting Started

This guide is for human contributors joining the ZingBang org. It covers the essentials: workstation setup, repo layout, architecture basics, and how we ship.

## What we are building

ZingBang is a developer-first platform for globally available services. We are building a control plane plus cross-cloud runtime foundations with strong resilience and clear operational semantics.

## Accounts and access you will need

- GitHub access to `Kismet-Engineering`
- Plane access to the ZingBang workspace
- 1Password access to the `workstation` vault for shared credentials

## Workstation setup (baseline)

We standardize on Colima as the local container runtime. Install the core tools:

```bash
brew install colima docker mise gh kubectl kind subctl
```

Start Colima once after install:

```bash
colima start
```

Quick sanity checks:

```bash
mise --version
gh --version
docker --version
kubectl version --client
kind --version
subctl version
```

## Clone and layout

We keep all repos under a single workspace directory:

```
~/dev/zingbang/
  zingbang_workspace/
  zingbang_platform_api/
  zingbang_foundations/
  zingbang_cluster_ops/
  zingbang_local_experiments/
  zingbang_business/
  zingbang_site/
```

Clone the repos you need for your work. Each repo is autonomous and owns its own tooling and tasks.

## Repository map

- `zingbang_platform_api`
  - Control plane API and contracts
  - Hosted customer/admin dashboards, onboarding flows, auth/session, billing and event model, docs

- `zingbang_foundations`
  - Cloud infrastructure foundations (OpenTofu)
  - AWS/GCP environment bootstrap and federation prerequisites

- `zingbang_cluster_ops`
  - GitOps source-of-truth for runtime components
  - Flux reconciliation, environment overlays, ops config

- `zingbang_local_experiments`
  - E2E experiments and validation sandboxes
  - Local federation runs used to de-risk architecture decisions

- `zingbang_site`
  - Public-facing product site and docs presentation
  - Marketing/docs shell only; not the hosted customer or admin dashboards

- `zingbang_business`
  - Strategy, planning artifacts, ADRs, and roadmap context

## High-level architecture

ZingBang has two planes:

- **Platform admin plane**: management API at `api.zingbang.io`
- **Customer runtime plane**: workload/data plane at `apps.zingbang.io`

Flow at a glance:

1. Platform API defines contracts and lifecycle semantics.
2. Foundations and cluster-ops establish the runtime substrate in AWS/GCP.
3. Local experiments validate federation behaviors and operational evidence.
4. Site and docs communicate the system clearly to users.

## Dashboard surfaces and code ownership

ZingBang also exposes two hosted dashboard surfaces in addition to the public site and API:

- `app.zingbang.io` - customer-facing hosted dashboard
- `admin.zingbang.io` - internal operator/admin dashboard

Those dashboards are implemented inside `zingbang_platform_api`, not `zingbang_site`.

- Customer dashboard frontend bundle: `../zingbang_platform_api/customer_dashboard_web`
- Admin dashboard frontend bundle: `../zingbang_platform_api/platform_admin_web`
- Static serving and host-based routing: `../zingbang_platform_api/internal/api/static.go`
- Hosted auth/session handlers: `../zingbang_platform_api/internal/api/auth_tokens.go`
- Dashboard-backed API routes: `../zingbang_platform_api/internal/api/server.go`

That means:

- use `zingbang_site` for marketing pages, docs IA, onboarding/help content, and public-site presentation
- use `zingbang_platform_api` for customer dashboard UI, admin dashboard UI, dashboard auth/session, and customer-safe read APIs that power those dashboards

## Delivery pipeline and responsibilities

We orchestrate changes through a tight cross-repo delivery pipeline so every plane stays aligned. The simplified dependency graph below shows how a change typically propagates.

```mermaid
flowchart LR
    ZA[zingbang_platform_api (control plane)] --> ZC[zingbang_cluster_ops (runtime config)]
    ZF[zingbang_foundations (cloud infra)] --> ZC
    ZC --> ZLE[zingbang_local_experiments CI]
    ZC --> Managed[Managed clusters (dev/stage/prod)]
    ZLE --> CI[CI evidence / regression suites]
    ZA --> Managed
```

### Roles & flow

1. **Platform API** owns the control plane code that interacts with tenants, billing, migrations, and exposes contracts to the runtime.
2. **Foundations** targets the cloud provider primitives (AWS/GCP) using OpenTofu and publishes outputs consumed by runtime overlays.
3. **Cluster Ops** stitches together runtime manifests and mirror repositories (Flux). It consumes artifacts from platform-api/foundations and deploys them to the managed clusters.
4. **Local Experiments** pull the same images/manifests that cluster-ops deploys and run federation E2E locally (kind + Colima) to provide fast developer feedback.
5. **Site** owns the marketing/docs experience at `zingbang.io`, while the platform API service owns the hosted dashboard surfaces at `app.zingbang.io` and `admin.zingbang.io`.

### Development checklist

- If you touch the API or migrations, merge the change in `zingbang_platform_api`, then let `release-and-promote.yml` publish an image and open a cluster-ops PR. Merge the cluster-ops PR before expecting the new functionality to reach the managed/dev clusters.
- If you update infrastructure (foundations), capture new outputs in `zingbang_cluster_ops` so those manifests reference the revised resources.
- When debugging runtime failures locally, run `zingbang_local_experiments` workflows after ensuring your local cluster-ops state reflects the latest promoted config (e.g., by pulling the merged PR or running `platform-api:image:load`).

## How we work (Plane + GitHub)

- Plane is the source of truth for task state.
- Use `Platform Milestones` for cross-repo milestones and repo-aligned projects for execution: `Platform API`, `Foundations`, `Cluster Ops`, `Local Experiments`, `Site`, and `Go-To-Market`.
- Keep labels lightweight: use `type:*` and `horizon:*`; add `milestone` only when it helps planning; avoid `track:*` and `component:*` on new tickets.
- Commit messages are short, imperative, and include the Plane issue ID.
- PRs and issues should link to each other and include validation notes.
- When closing a Plane ticket, add a comment that links to the PR/commit and summarizes evidence delivered.

## Versioning and release process

### Platform API images

- Merges to `main` in `zingbang_platform_api` publish container images to GHCR.
- The release workflow publishes `sha-<commit>` images and a `dev` tag by default.
- The same workflow opens a promotion PR in `zingbang_cluster_ops` to update runtime image tags.

### GitOps promotion

- `zingbang_cluster_ops` is the runtime source-of-truth.
- Promotion is done via PRs that update image tags and env overlays; Flux reconciles the changes.

### Business releases and changelog

- Release notes and changelog live in `zingbang_business/docs/releases/`.
- Use those docs for user-facing release summaries and internal release tracking.

## Common workflows

Platform API to runtime promotion:

1. Merge to `main` in `zingbang_platform_api`.
2. `release-and-promote.yml` builds and publishes GHCR images.
3. A PR is created in `zingbang_cluster_ops` updating the image tag.
4. Merge the cluster-ops PR to deploy to dev clusters.

Local federation E2E:

1. `zingbang_local_experiments` CI pulls the platform API image.
2. Creates kind clusters with Submariner mesh.
3. Deploys Yugabyte and runs migrations.
4. Executes federation lifecycle tests.

Infra changes:

1. Edit OpenTofu in `zingbang_foundations`.
2. Run `mise run tofu:plan:dev` and review output.
3. Apply changes and export outputs.
4. Update downstream consumers if output shapes change.

## Where to look next

- `zingbang_workspace/AGENTS.md` for conventions and shared workflows
- `zingbang_platform_api/README.md` for API setup and release automation
- `zingbang_local_experiments/README.md` for Colima-based local E2E flows
- `zingbang_business/docs/releases/` for release notes and changelog
