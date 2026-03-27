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
| [zingbang_platform_api](../zingbang_platform_api) | Platform admin plane API (Go) |
| [zingbang_local_experiments](../zingbang_local_experiments) | Local federation E2E, kind/Submariner |
| [zingbang_foundations](../zingbang_foundations) | Cloud infra (OpenTofu) |
| [zingbang_cluster_ops](../zingbang_cluster_ops) | Cluster manifests, GitOps |
| [zingbang_business](../zingbang_business) | ADRs, briefs, docs |
| [zingbang_site](../zingbang_site) | Product/site |

## Documentation

See [AGENTS.md](./AGENTS.md) for full context including conventions, workflows, and commands.

## Plane project model

- `Platform Milestones` owns cross-repo milestones and delivery outcomes.
- `Platform API`, `Foundations`, `Cluster Ops`, `Local Experiments`, and `Site` own repo-aligned execution.
- `Go-To-Market` owns market/customer/business execution.
- `Legacy - Platform Delivery` is legacy history only.
