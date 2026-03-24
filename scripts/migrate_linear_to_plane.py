#!/usr/bin/env python3
"""Migrate Linear projects/issues/comments to Plane.

Usage:
    python scripts/migrate_linear_to_plane.py          # full migration
    python scripts/migrate_linear_to_plane.py --init   # single-project/issue test pass
    python scripts/migrate_linear_to_plane.py --reset  # clear migration state (re-run from scratch)

--init mode:
  - Migrates 1 Linear project → Plane project, ALL states/labels for it, 1 issue, ALL its comments
  - On re-runs: skips structural resources, UPDATES work items/comments so fixes are visible

--reset:
  - Deletes migration_state.json so the next run starts fresh
  - You must also manually delete any Plane projects created by a previous run

State schema (migration_state.json):
  {
    "projects": { "<linear_project_id|_teamless>": "<plane_project_id>" },
    "states":   { "<plane_project_id>:<linear_state_id>": "<plane_state_id>" },
    "labels":   { "<plane_project_id>:<linear_label_id>": "<plane_label_id>" },
    "issues":   { "<linear_issue_id>": {"work_item_id": "...", "project_id": "..."} },
    "comments": { "<linear_comment_id>": "<plane_comment_id>" }
  }

Required environment variables:
    LINEAR_API_KEY         Linear personal API key
    PLANE_API_KEY          Plane API key
    PLANE_WORKSPACE_SLUG   Plane workspace slug (e.g. "zingbang")
    PLANE_BASE_URL         Self-hosted Plane base URL (e.g. "https://plane.example.com")
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import markdown2
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LINEAR_GRAPHQL = "https://api.linear.app/graphql"
STATE_FILE = Path(__file__).parent / "migration_state.json"

PRIORITY_MAP = {0: "none", 1: "urgent", 2: "high", 3: "medium", 4: "low"}

STATE_GROUP_MAP = {
    "backlog": "backlog",
    "unstarted": "unstarted",
    "started": "started",
    "completed": "completed",
    "cancelled": "cancelled",
    "triage": "backlog",
}

TEAMLESS_KEY = "_teamless"
TEAMLESS_PROJECT_NAME = "Uncategorized"


def get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: missing required env var {name}", file=sys.stderr)
        sys.exit(1)
    return val


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"projects": {}, "states": {}, "labels": {}, "issues": {}, "comments": {}}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def state_key(plane_project_id: str, linear_id: str) -> str:
    """Compound key for project-scoped resources (states, labels)."""
    return f"{plane_project_id}:{linear_id}"


# ---------------------------------------------------------------------------
# Linear API (GraphQL)
# ---------------------------------------------------------------------------

def linear_post(query: str, variables: dict, api_key: str) -> dict:
    resp = requests.post(
        LINEAR_GRAPHQL,
        json={"query": query, "variables": variables},
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Linear GraphQL error: {data['errors']}")
    return data["data"]


def linear_paginate(query: str, variables: dict, path: list[str], api_key: str) -> list:
    results = []
    cursor = None
    while True:
        vars_ = {**variables, "after": cursor}
        data = linear_post(query, vars_, api_key)
        node = data
        for key in path:
            node = node[key]
        results.extend(node["nodes"])
        if not node["pageInfo"]["hasNextPage"]:
            break
        cursor = node["pageInfo"]["endCursor"]
    return results


def linear_get_teams(api_key: str) -> list:
    q = """
    query Teams($after: String) {
      teams(first: 50, after: $after) {
        nodes { id name key description }
        pageInfo { hasNextPage endCursor }
      }
    }
    """
    return linear_paginate(q, {}, ["teams"], api_key)


def linear_get_projects(api_key: str) -> list:
    q = """
    query Projects($after: String) {
      projects(first: 50, after: $after) {
        nodes { id name description }
        pageInfo { hasNextPage endCursor }
      }
    }
    """
    return linear_paginate(q, {}, ["projects"], api_key)


def linear_get_workflow_states(team_id: str, api_key: str) -> list:
    q = """
    query States($teamId: String!, $after: String) {
      team(id: $teamId) {
        states(first: 100, after: $after) {
          nodes { id name type color }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    return linear_paginate(q, {"teamId": team_id}, ["team", "states"], api_key)


def linear_get_team_labels(team_id: str, api_key: str) -> list:
    q = """
    query Labels($teamId: String!, $after: String) {
      team(id: $teamId) {
        labels(first: 100, after: $after) {
          nodes { id name color }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    return linear_paginate(q, {"teamId": team_id}, ["team", "labels"], api_key)


def linear_get_project_labels(project_id: str, api_key: str) -> list:
    q = """
    query ProjectLabels($projectId: String!, $after: String) {
      project(id: $projectId) {
        labels(first: 100, after: $after) {
          nodes { id name color }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    try:
        return linear_paginate(q, {"projectId": project_id}, ["project", "labels"], api_key)
    except Exception as e:
        print(f"  warn: could not fetch project labels for {project_id}: {e}")
        return []


def linear_get_issues(team_id: str, api_key: str) -> list:
    q = """
    query Issues($teamId: String!, $after: String) {
      team(id: $teamId) {
        issues(first: 50, after: $after) {
          nodes {
            id
            identifier
            title
            description
            priority
            project { id }
            state { id name type }
            labels { nodes { id name } }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    return linear_paginate(q, {"teamId": team_id}, ["team", "issues"], api_key)


def linear_get_comments(issue_id: str, api_key: str) -> list:
    q = """
    query Comments($issueId: String!, $after: String) {
      issue(id: $issueId) {
        comments(first: 50, after: $after) {
          nodes { id body createdAt }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """
    return linear_paginate(q, {"issueId": issue_id}, ["issue", "comments"], api_key)


# ---------------------------------------------------------------------------
# Plane API (REST)
# ---------------------------------------------------------------------------

class PlaneClient:
    def __init__(self, base_url: str, api_key: str, workspace_slug: str):
        self.base = base_url.rstrip("/") + "/api/v1"
        self.slug = workspace_slug
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key, "Content-Type": "application/json"})
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        self._last_request = time.monotonic()

    def _url(self, path: str) -> str:
        return f"{self.base}/workspaces/{self.slug}/{path}"

    def post(self, path: str, payload: dict) -> dict:
        self._throttle()
        resp = self.session.post(self._url(path), json=payload, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"Plane POST {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def patch(self, path: str, payload: dict) -> dict:
        self._throttle()
        resp = self.session.patch(self._url(path), json=payload, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"Plane PATCH {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def get(self, path: str) -> dict:
        self._throttle()
        resp = self.session.get(self._url(path), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def post_or_existing(self, path: str, payload: dict) -> tuple[dict, bool]:
        """POST and return (result, created). On 409, extract the existing resource ID."""
        self._throttle()
        resp = self.session.post(self._url(path), json=payload, timeout=30)
        if resp.status_code == 409:
            body = resp.json()
            if "id" in body:
                return {"id": body["id"]}, False
            raise RuntimeError(f"Plane 409 {path} but no id in response: {resp.text}")
        if not resp.ok:
            raise RuntimeError(f"Plane POST {path} -> {resp.status_code}: {resp.text}")
        return resp.json(), True

    def create_project(self, name: str, description: str = "") -> dict:
        # Identifier: alphanumeric, max 12 chars
        ident = "".join(c for c in name.upper() if c.isalnum())[:12] or "PROJ"
        return self.post("projects/", {
            "name": name,
            "identifier": ident,
            "description": description or "",
            "network": 2,
        })

    def create_state(self, project_id: str, name: str, group: str, color: str = "#666666") -> tuple[dict, bool]:
        return self.post_or_existing(f"projects/{project_id}/states/", {
            "name": name,
            "group": group,
            "color": color or "#666666",
        })

    def create_label(self, project_id: str, name: str, color: str = "#666666") -> tuple[dict, bool]:
        return self.post_or_existing(f"projects/{project_id}/labels/", {
            "name": name,
            "color": color or "#666666",
        })

    def create_work_item(self, project_id: str, payload: dict) -> dict:
        return self.post(f"projects/{project_id}/work-items/", payload)

    def update_work_item(self, project_id: str, wi_id: str, payload: dict) -> dict:
        return self.patch(f"projects/{project_id}/work-items/{wi_id}/", payload)

    def create_comment(self, project_id: str, work_item_id: str, body_html: str) -> dict:
        return self.post(f"projects/{project_id}/work-items/{work_item_id}/comments/", {
            "comment_html": body_html,
        })

    def update_comment(self, project_id: str, work_item_id: str, comment_id: str, body_html: str) -> dict:
        return self.patch(
            f"projects/{project_id}/work-items/{work_item_id}/comments/{comment_id}/",
            {"comment_html": body_html},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def md_to_html(text: str) -> str:
    if not text:
        return ""
    return markdown2.markdown(
        text,
        extras=["fenced-code-blocks", "tables", "strike", "cuddled-lists"],
    )


def build_work_item_payload(issue: dict, state: dict, plane_project_id: str, for_update: bool = False) -> dict:
    identifier_note = f"<p><strong>[LINEAR: {issue['identifier']}]</strong></p>"
    body_html = identifier_note + md_to_html(issue.get("description") or "")

    # States and labels are project-scoped — use compound key
    plane_state_id = None
    if issue.get("state"):
        k = state_key(plane_project_id, issue["state"]["id"])
        plane_state_id = state["states"].get(k)

    plane_label_ids = []
    for lbl in issue.get("labels", {}).get("nodes", []):
        k = state_key(plane_project_id, lbl["id"])
        mapped = state["labels"].get(k)
        if mapped:
            plane_label_ids.append(mapped)

    priority = PRIORITY_MAP.get(issue.get("priority", 0), "none")
    title = f"[{issue['identifier']}] {issue['title']}"

    payload = {
        "name": title,
        "description_html": body_html,
        "priority": priority,
    }
    if plane_state_id:
        payload["state"] = plane_state_id
    # Plane's work-items endpoint uses "labels" (not "label_ids") for the M2M field.
    # For PATCH (update), always include it — Plane treats an omitted M2M field as "clear to empty".
    # For POST (create), only include when non-empty.
    if for_update or plane_label_ids:
        payload["labels"] = plane_label_ids
    return payload


def migrate_states_for_project(plane, state, plane_project_id: str, workflow_states: list):
    """Create all Linear workflow states in a given Plane project."""
    for ws in workflow_states:
        k = state_key(plane_project_id, ws["id"])
        if k in state["states"]:
            print(f"    skip state '{ws['name']}' (already migrated)")
            continue
        group = STATE_GROUP_MAP.get(ws["type"], "backlog")
        s, created = plane.create_state(plane_project_id, ws["name"], group, ws.get("color"))
        state["states"][k] = s["id"]
        save_state(state)
        verb = "created" if created else "mapped  "
        print(f"    {verb} state '{ws['name']}' ({group}) -> {s['id']}")


def migrate_labels_for_project(plane, state, plane_project_id: str, all_labels: list):
    """Create all labels in a given Plane project."""
    for label in all_labels:
        k = state_key(plane_project_id, label["id"])
        if k in state["labels"]:
            print(f"    skip label '{label['name']}' (already migrated)")
            continue
        lbl, created = plane.create_label(plane_project_id, label["name"], label.get("color"))
        state["labels"][k] = lbl["id"]
        save_state(state)
        verb = "created" if created else "mapped  "
        print(f"    {verb} label '{label['name']}' -> {lbl['id']}")


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def run_migration(init_mode: bool):
    linear_key = get_env("LINEAR_API_KEY")
    plane_key = get_env("PLANE_API_KEY")
    workspace_slug = get_env("PLANE_WORKSPACE_SLUG")
    plane_base_url = get_env("PLANE_BASE_URL")

    plane = PlaneClient(plane_base_url, plane_key, workspace_slug)
    state = load_state()

    mode_label = "[INIT]" if init_mode else "[FULL]"
    print(f"{mode_label} Starting Linear → Plane migration")

    # -----------------------------------------------------------------------
    # Fetch Linear source data
    # -----------------------------------------------------------------------
    print("\n  Fetching Linear data...")
    teams = linear_get_teams(linear_key)
    team = teams[0]  # single team workspace
    linear_projects = linear_get_projects(linear_key)
    workflow_states = linear_get_workflow_states(team["id"], linear_key)
    team_labels = linear_get_team_labels(team["id"], linear_key)

    if init_mode:
        linear_projects = linear_projects[:1]

    print(f"  Found {len(linear_projects)} Linear projects, {len(workflow_states)} states, {len(team_labels)} team labels")

    # -----------------------------------------------------------------------
    # 1. Linear projects → Plane projects
    # -----------------------------------------------------------------------
    print("\n--- Projects ---")

    # Ensure teamless catch-all exists
    if TEAMLESS_KEY not in state["projects"]:
        p = plane.create_project(TEAMLESS_PROJECT_NAME, "Issues not associated with a Linear project")
        state["projects"][TEAMLESS_KEY] = p["id"]
        save_state(state)
        print(f"  created catch-all project '{TEAMLESS_PROJECT_NAME}' -> {p['id']}")
    else:
        print(f"  skip catch-all project (already migrated)")

    for lp in linear_projects:
        if lp["id"] in state["projects"]:
            print(f"  skip project '{lp['name']}' (already migrated)")
            continue
        p = plane.create_project(lp["name"], lp.get("description") or "")
        state["projects"][lp["id"]] = p["id"]
        save_state(state)
        print(f"  created project '{lp['name']}' -> {p['id']}")

    # -----------------------------------------------------------------------
    # 2. States — in every Plane project (project-scoped in Plane)
    # -----------------------------------------------------------------------
    print("\n--- States ---")
    for linear_proj_id, plane_proj_id in state["projects"].items():
        print(f"  project {plane_proj_id[:8]}...")
        migrate_states_for_project(plane, state, plane_proj_id, workflow_states)

    # -----------------------------------------------------------------------
    # 3. Labels — team labels + project labels, in every Plane project
    # -----------------------------------------------------------------------
    print("\n--- Labels ---")

    # Collect all unique labels: team-level + per-project
    all_label_ids = {lbl["id"]: lbl for lbl in team_labels}
    for lp in linear_projects:
        for lbl in linear_get_project_labels(lp["id"], linear_key):
            all_label_ids[lbl["id"]] = lbl
    all_labels = list(all_label_ids.values())
    print(f"  {len(all_labels)} unique labels (team + project-level)")

    for linear_proj_id, plane_proj_id in state["projects"].items():
        print(f"  project {plane_proj_id[:8]}...")
        migrate_labels_for_project(plane, state, plane_proj_id, all_labels)

    # -----------------------------------------------------------------------
    # 4. Issues → Work Items
    # -----------------------------------------------------------------------
    print("\n--- Work Items ---")
    all_issues = linear_get_issues(team["id"], linear_key)
    if init_mode:
        all_issues = all_issues[:1]

    for issue in all_issues:
        linear_proj_id = (issue.get("project") or {}).get("id") or TEAMLESS_KEY
        plane_proj_id = state["projects"].get(linear_proj_id)

        if not plane_proj_id:
            # Project wasn't migrated yet (e.g. not in init batch) — use teamless
            plane_proj_id = state["projects"][TEAMLESS_KEY]

        if issue["id"] in state["issues"]:
            if init_mode:
                meta = state["issues"][issue["id"]]
                # Build payload using the project the work item actually lives in,
                # so state/label compound-key lookups resolve against the right project.
                # for_update=True ensures label_ids is always included (Plane clears M2M on omission).
                update_payload = build_work_item_payload(issue, state, meta["project_id"], for_update=True)
                plane.update_work_item(meta["project_id"], meta["work_item_id"], update_payload)
                print(f"  updated  '[{issue['identifier']}] {issue['title'][:55]}' (init re-apply)")
            else:
                print(f"  skip '{issue['identifier']}' (already migrated)")
            continue

        payload = build_work_item_payload(issue, state, plane_proj_id)
        wi = plane.create_work_item(plane_proj_id, payload)
        state["issues"][issue["id"]] = {"work_item_id": wi["id"], "project_id": plane_proj_id}
        save_state(state)
        print(f"  created  '[{issue['identifier']}] {issue['title'][:55]}' -> {wi['id']}")

    # -----------------------------------------------------------------------
    # 5. Comments — all comments for all processed issues
    # -----------------------------------------------------------------------
    print("\n--- Comments ---")
    issue_entries = list(state["issues"].items())
    if init_mode:
        issue_entries = issue_entries[:1]

    for linear_issue_id, issue_meta in issue_entries:
        work_item_id = issue_meta["work_item_id"]
        project_id = issue_meta["project_id"]

        for comment in linear_get_comments(linear_issue_id, linear_key):
            body_html = md_to_html(comment.get("body") or "")
            if not body_html:
                continue

            existing = state["comments"].get(comment["id"])
            if existing is not None:
                if init_mode and isinstance(existing, str):
                    plane.update_comment(project_id, work_item_id, existing, body_html)
                    print(f"  updated  comment {comment['id'][:8]}... (init re-apply)")
                else:
                    print(f"  skip comment {comment['id'][:8]}...")
                continue

            result = plane.create_comment(project_id, work_item_id, body_html)
            state["comments"][comment["id"]] = result["id"]
            save_state(state)
            print(f"  created  comment {comment['id'][:8]}... -> {result['id'][:8]}...")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{mode_label} Done.")
    print(f"  projects: {len(state['projects'])}")
    print(f"  states:   {len(state['states'])}")
    print(f"  labels:   {len(state['labels'])}")
    print(f"  issues:   {len(state['issues'])}")
    print(f"  comments: {len(state['comments'])}")


# ---------------------------------------------------------------------------
# Label reconciliation
# ---------------------------------------------------------------------------

def run_reconcile_labels():
    """
    Re-apply correct labels to all already-migrated work items.

    Idempotent: safe to run multiple times. Does not modify migration_state.json.
    Useful when labels were created in Plane but not associated with work items.

    Tries both 'label_ids' and 'labels' field names and reports which worked.
    """
    linear_key = get_env("LINEAR_API_KEY")
    plane_key = get_env("PLANE_API_KEY")
    workspace_slug = get_env("PLANE_WORKSPACE_SLUG")
    plane_base_url = get_env("PLANE_BASE_URL")

    plane = PlaneClient(plane_base_url, plane_key, workspace_slug)
    state = load_state()

    if not state["issues"]:
        print("No migrated issues found in state. Run migration first.")
        return

    print("[RECONCILE-LABELS] Re-applying labels to all migrated work items...")

    # Build a lookup: linear_issue_id -> issue data
    print("\n  Fetching Linear issues...")
    teams = linear_get_teams(linear_key)
    all_issues = linear_get_issues(teams[0]["id"], linear_key)
    issue_by_id = {i["id"]: i for i in all_issues}
    print(f"  Fetched {len(all_issues)} Linear issues")

    patched = skipped_no_labels = skipped_not_found = missing_mappings = 0

    print("\n--- Patching work item labels ---")
    for linear_issue_id, issue_meta in state["issues"].items():
        issue = issue_by_id.get(linear_issue_id)
        if not issue:
            print(f"  WARN: Linear issue {linear_issue_id[:8]}... not found in current data, skipping")
            skipped_not_found += 1
            continue

        linear_labels = issue.get("labels", {}).get("nodes", [])
        if not linear_labels:
            skipped_no_labels += 1
            continue

        plane_proj_id = issue_meta["project_id"]
        plane_wi_id = issue_meta["work_item_id"]

        plane_label_ids = []
        for lbl in linear_labels:
            k = state_key(plane_proj_id, lbl["id"])
            mapped = state["labels"].get(k)
            if mapped:
                plane_label_ids.append(mapped)
            else:
                print(f"  WARN: no Plane label for '{lbl['name']}' in project {plane_proj_id[:8]}... (key {k[:24]}...)")
                missing_mappings += 1

        if not plane_label_ids:
            print(f"  skip '{issue['identifier']}': {len(linear_labels)} Linear label(s) but none mapped to Plane")
            missing_mappings += len(linear_labels)
            continue

        # "labels" is the correct field for Plane's work-items endpoint (not "label_ids").
        patch_payload = {"labels": plane_label_ids}
        plane.update_work_item(plane_proj_id, plane_wi_id, patch_payload)
        label_names = ", ".join(lbl["name"] for lbl in linear_labels)
        print(f"  patched '{issue['identifier']}': [{label_names}]")
        patched += 1

    print(f"\n[RECONCILE-LABELS] Done.")
    print(f"  patched:             {patched}")
    print(f"  skipped (no labels): {skipped_no_labels}")
    print(f"  skipped (not found): {skipped_not_found}")
    print(f"  missing mappings:    {missing_mappings}")
    if missing_mappings:
        print("  NOTE: missing mappings mean those labels exist in Linear but weren't found")
        print("  in state['labels']. Re-run full migration to pick them up.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Linear → Plane")
    parser.add_argument("--init", action="store_true",
                        help="Test pass: 1 project, all states/labels, 1 issue, all its comments; re-runs update content")
    parser.add_argument("--reset", action="store_true",
                        help="Delete migration_state.json to start fresh (also manually delete Plane projects)")
    parser.add_argument("--reconcile-labels", action="store_true",
                        help="Re-apply correct labels to all migrated work items (idempotent, no state changes)")
    args = parser.parse_args()

    if args.reset:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            print(f"Deleted {STATE_FILE}")
        else:
            print("No state file found, nothing to reset.")
        print("REMINDER: also manually delete any Plane projects created by the previous run.")
        sys.exit(0)

    if args.reconcile_labels:
        run_reconcile_labels()
        sys.exit(0)

    run_migration(init_mode=args.init)
