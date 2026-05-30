#!/usr/bin/env python3
"""
Semgrep → Azure DevOps Ticket Creator

Creates Azure DevOps work items for Semgrep findings with configurable filters:
- SAST: severity + confidence
- SCA: severity + reachability (exposures) + transitivity
- License: SBOM licenses vs whitelist

Configuration is passed via Azure Pipelines env vars (set by task.ts):
- SEMGREP_APP_TOKEN, DEPLOYMENT_ID
- ENABLE_TICKET_CREATION, TICKET_TYPES
- SAST_SEVERITIES, SAST_CONFIDENCES
- SCA_SEVERITIES, SCA_REACHABILITIES
- USE_DEFAULT_LICENSE_WHITELIST, LICENSE_WHITELIST_OVERRIDE
- ITERATION_LIST_CSV_URL, AZURE_DEV_PATH_CSV_URL, DEFAULT_ITERATION_PATH

Required Azure DevOps env vars:
- SYSTEM_ACCESSTOKEN
- SYSTEM_COLLECTIONURI, SYSTEM_TEAMPROJECTID
- BUILD_REPOSITORY_ID, BUILD_REPOSITORY_URI, BUILD_REPOSITORY_NAME
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import requests

from api_utils import (
    ado_auth_tuple,
    extract_semgrep_findings,
    git_branch_ref,
    resolve_semgrep_repo_name,
)


DEFAULT_APPROVED_LICENSES: Set[str] = {
    "0BSD", "AFL-2.1", "AGPL-3.0", "Apache-2.0", "Artistic-2.0",
    "BlueOak-1.0.0", "BSD-2-Clause", "BSD-2-Clause-FreeBSD",
    "BSD-3-Clause", "BSD-4-Clause", "CC0-1.0", "CC-BY-*", "CC-BY-4.0",
    "EUPL-1.2", "GPL-2.0", "GPL-3.0", "Hippocratic-2.1", "HPND", "ISC",
    "JSON", "LGPL-2.1", "LGPL-3.0", "Zlib", "MIT", "MIT-0", "MPL-2.0",
    "ODC-By-1.0", "Python-2.0", "Ruby", "Unlicense", "WTFPL", "X11",
    "ZPL-2.1", "MPL-1.1", "MS-PL", "OFL-1.1", "non-standard", "PSF-2.0",
}


def _log_level() -> int:
    lvl = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    return getattr(logging, lvl, logging.INFO)


logging.basicConfig(level=_log_level(), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ticket_creator")


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _split_csvish(v: str) -> List[str]:
    if not v:
        return []
    parts = re.split(r"[,\n\r]+", v)
    return [p.strip() for p in parts if p.strip()]


def _normalize_choice(s: str) -> str:
    return s.strip().lower().replace(" ", "_")


def _ado_auth() -> Tuple[str, str]:
    return ado_auth_tuple()


def _normalize_ado_path(path: str) -> str:
    path = path.strip().replace("/", "\\")
    while path.startswith("\\"):
        path = path[1:]
    return path


def _parse_ado_org(collection_uri: str) -> str:
    uri = (collection_uri or "").rstrip("/")
    if "dev.azure.com/" in uri:
        return uri.split("dev.azure.com/", 1)[1].split("/")[0]
    if ".visualstudio.com" in uri:
        return uri.split("//", 1)[1].split(".visualstudio.com", 1)[0]
    return ""


def _resolve_ado_org() -> str:
    return os.getenv("ADO_ORGANIZATION", "").strip() or _parse_ado_org(
        os.getenv("SYSTEM_COLLECTIONURI", "")
    )


def _resolve_ado_project() -> str:
    return os.getenv("ADO_PROJECT", "").strip() or os.getenv("SYSTEM_TEAMPROJECT", "").strip()


def _resolve_ado_team(session: requests.Session, org: str, project: str, auth: Tuple[str, str]) -> str:
    configured = os.getenv("ADO_TEAM", "").strip()
    if configured:
        return configured
    url = f"https://dev.azure.com/{org}/_apis/projects/{project}/teams?api-version=7.1"
    try:
        r = session.get(url, auth=auth, timeout=30)
        r.raise_for_status()
        teams = r.json().get("value") or []
        if not teams:
            return project
        for team in teams:
            if team.get("name") == project:
                return project
        name = teams[0].get("name") or project
        logger.info("Auto-selected ADO team: %s", name)
        return name
    except Exception as e:
        logger.warning("Could not list ADO teams, using project name: %s", e)
        return project


def _fetch_default_area_path(session: requests.Session, org: str, project: str, auth: Tuple[str, str]) -> str:
    """Fetch project area root when defaultAreaPath is not configured."""
    url = (
        f"https://dev.azure.com/{org}/{project}/_apis/wit/classificationnodes/areas"
        f"?$depth=2&api-version=7.1"
    )
    try:
        r = session.get(url, auth=auth, timeout=30)
        if r.status_code != 200:
            return ""
        data = r.json() or {}
        root = _normalize_ado_path(data.get("path") or "")
        children = data.get("children") or []
        if children and children[0].get("path"):
            return _normalize_ado_path(children[0]["path"])
        return root
    except Exception as e:
        logger.warning("Failed to fetch default area path: %s", e)
        return ""


def _is_sca_cli_result(result: Dict[str, Any]) -> bool:
    check_id = str(result.get("check_id") or "")
    if check_id.startswith("ssc-") or check_id.startswith("supply-chain."):
        return True
    extra = result.get("extra") or {}
    return bool(extra.get("sca-info") or extra.get("sca_info"))


def _cli_result_to_finding(result: Dict[str, Any]) -> Dict[str, Any]:
    extra = result.get("extra") or {}
    meta = extra.get("metadata") or {}
    start = result.get("start") or {}
    end = result.get("end") or {}
    sca_info = extra.get("sca-info") or extra.get("sca_info") or {}
    return {
        "severity": extra.get("severity") or meta.get("severity") or "medium",
        "confidence": meta.get("confidence") or extra.get("confidence") or "medium",
        "rule": {
            "name": result.get("check_id") or "",
            "message": extra.get("message") or "",
            "confidence": meta.get("confidence") or extra.get("confidence"),
        },
        "rule_name": result.get("check_id") or "",
        "rule_message": extra.get("message") or "",
        "location": {
            "file_path": result.get("path") or "",
            "filePath": result.get("path") or "",
            "line": start.get("line") or 1,
            "column": start.get("col") or start.get("column") or 1,
            "end_line": end.get("line") or start.get("line") or 1,
        },
        "reachability": sca_info.get("reachability") or "",
        "relevant_since": extra.get("relevant_since") or "",
        "id": result.get("fingerprint") or result.get("check_id"),
    }


def _load_findings_from_cli_json(path: str, issue_type: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read findings file %s: %s", path, e)
        return []

    results = data.get("results") or []
    want_sca = issue_type.lower() == "sca"
    converted: List[Dict[str, Any]] = []
    for result in results:
        is_sca = _is_sca_cli_result(result)
        if want_sca != is_sca:
            continue
        converted.append(_cli_result_to_finding(result))
    if converted:
        logger.info("Loaded %d %s finding(s) from %s", len(converted), issue_type.upper(), path)
    return converted


def _fetch_current_iteration_from_ado(
    session: requests.Session,
    org: str,
    project: str,
    team: str,
    auth: Tuple[str, str],
) -> Optional[str]:
    """Fetch the current sprint iteration path from Azure DevOps team settings."""
    url = (
        f"https://dev.azure.com/{org}/{project}/{team}/_apis/work/teamsettings/iterations"
        f"?$timeframe=current&api-version=7.1"
    )
    try:
        r = session.get(url, auth=auth, timeout=30)
        if r.status_code == 404:
            logger.warning("Team iteration API returned 404 for team=%s", team)
            return None
        r.raise_for_status()
        iterations = r.json().get("value") or []
        if iterations:
            path = iterations[0].get("path") or iterations[0].get("name")
            if path:
                logger.info("Current sprint from ADO API: %s", path)
                return _normalize_ado_path(path)
    except Exception as e:
        logger.warning("Failed to fetch current iteration from team settings: %s", e)

    # Fallback: all iterations with dates — pick the one containing today
    url = (
        f"https://dev.azure.com/{org}/{project}/{team}/_apis/work/teamsettings/iterations"
        f"?api-version=7.1"
    )
    try:
        r = session.get(url, auth=auth, timeout=30)
        r.raise_for_status()
        today = datetime.now(timezone.utc).date()
        for item in r.json().get("value") or []:
            attrs = item.get("attributes") or {}
            start_raw = attrs.get("startDate")
            finish_raw = attrs.get("finishDate")
            if not start_raw or not finish_raw:
                continue
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).date()
            finish = datetime.fromisoformat(finish_raw.replace("Z", "+00:00")).date()
            if start <= today <= finish:
                path = item.get("path") or item.get("name")
                if path:
                    logger.info("Matched sprint by date from ADO API: %s", path)
                    return _normalize_ado_path(path)
    except Exception as e:
        logger.warning("Failed to match iteration by date: %s", e)

    return None


def _fetch_iteration_from_classification_nodes(
    session: requests.Session,
    org: str,
    project: str,
    auth: Tuple[str, str],
) -> Optional[str]:
    """List iteration nodes (no dates) — returns deepest leaf path as last resort."""
    url = (
        f"https://dev.azure.com/{org}/{project}/_apis/wit/classificationnodes/iterations"
        f"?$depth=10&api-version=7.1"
    )
    try:
        r = session.get(url, auth=auth, timeout=30)
        r.raise_for_status()
        deepest: Optional[str] = None
        depth = -1

        def walk(node: Dict[str, Any], level: int) -> None:
            nonlocal deepest, depth
            path = node.get("path") or ""
            if path and not node.get("hasChildren") and level > depth:
                deepest = path
                depth = level
            for child in node.get("children") or []:
                walk(child, level + 1)

        walk(r.json(), 0)
        if deepest:
            logger.info("Deepest iteration node from classification API: %s", deepest)
            return _normalize_ado_path(deepest)
    except Exception as e:
        logger.warning("Failed to fetch iteration classification nodes: %s", e)
    return None


def _resolve_iteration_path(
    session: requests.Session,
    auth: Tuple[str, str],
    default_iteration: str,
    iter_csv_path: str,
) -> str:
    if _env_bool("USE_ADO_ITERATION_API", True):
        org = _resolve_ado_org()
        project = _resolve_ado_project()
        if org and project:
            team = _resolve_ado_team(session, org, project, auth)
            path = _fetch_current_iteration_from_ado(session, org, project, team, auth)
            if not path:
                path = _fetch_iteration_from_classification_nodes(session, org, project, auth)
            if path:
                return path
        else:
            logger.warning(
                "Skipping ADO iteration API (org=%r project=%r). Set adoOrganization/adoProject or run in a pipeline.",
                org,
                project,
            )

    if os.path.exists(iter_csv_path):
        return _normalize_ado_path(_current_iteration_path(iter_csv_path, default_iteration))

    return _normalize_ado_path(default_iteration)


def _requests_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({"User-Agent": "semgrep-ado-ext/1.0"})
    return sess


def _parse_pipeline_time() -> Optional[datetime]:
    """
    Azure var looks like: '2023-09-18 07:49:42+00:00' or '2023-09-18 07:49:42'
    """
    raw = os.getenv("SYSTEM_PIPELINESTARTTIME", "")
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(raw[0:len(fmt.replace("%z", "+00:00"))] if "%z" in fmt else raw[0:19], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    try:
        # ISO-ish
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        logger.warning("Could not parse SYSTEM_PIPELINESTARTTIME=%r", raw)
        return None


def _parse_relevant_since(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    # Semgrep API examples: "2020-11-18 23:28:12.391807+00:00" or ISO
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        # drop micros if needed
        s2 = s.split(".")[0]
        dt = datetime.fromisoformat(s2.replace(" ", "T").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _download_to_file(url: str, dest: str, auth: Optional[Tuple[str, str]] = None) -> bool:
    if not url:
        return False
    sess = _requests_session()
    try:
        r = sess.get(url, auth=auth, timeout=60)
        if r.status_code != 200:
            logger.warning("Failed to download %s: %s %s", url, r.status_code, r.text[:200])
            return False
        with open(dest, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        logger.warning("Download failed for %s: %s", url, e)
        return False


def _current_iteration_path(iter_csv_path: str, default_iteration: str) -> str:
    today = datetime.now().date()
    try:
        with open(iter_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            # Attempt to skip header if present
            header = next(reader, None)
            if header and len(header) >= 3 and "date" in ",".join(h.lower() for h in header):
                pass
            else:
                # treat it as a row and rewind logic by reusing it
                if header:
                    row = header
                    if len(row) >= 3:
                        start = datetime.strptime(row[1].strip(), "%m/%d/%Y").date()
                        end = datetime.strptime(row[2].strip(), "%m/%d/%Y").date()
                        if start <= today <= end:
                            return row[0].strip()
            for row in reader:
                if len(row) < 3:
                    continue
                start = datetime.strptime(row[1].strip(), "%m/%d/%Y").date()
                end = datetime.strptime(row[2].strip(), "%m/%d/%Y").date()
                if start <= today <= end:
                    return row[0].strip()
    except Exception as e:
        logger.warning("Iteration CSV parse failed: %s", e)
    return default_iteration


def _area_path(area_csv_path: str, email: str, default_area: str) -> str:
    try:
        with open(area_csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("email_contributor") or "").strip().lower() == email.strip().lower():
                    return (row.get("area_path") or default_area).strip()
    except Exception as e:
        logger.warning("Area CSV parse failed: %s", e)
    return default_area


@dataclass
class AdoContext:
    collection_uri: str
    project_id: str
    repo_id: str
    repo_uri: str
    repo_name: str
    requested_for_email: str
    pr_id: str
    source_branch_name: str
    pipeline_start: Optional[datetime]


class AzureDevOpsClient:
    def __init__(self, ctx: AdoContext):
        self.ctx = ctx
        self.auth = _ado_auth()
        self.sess = _requests_session()

    def _wi_url(self) -> str:
        return f"{self.ctx.collection_uri}{self.ctx.project_id}/_apis/wit/workitems/$task"

    def _wiql_url(self) -> str:
        return f"{self.ctx.collection_uri}{self.ctx.project_id}/_apis/wit/wiql?api-version=7.0"

    def _escape_wiql(self, s: str) -> str:
        return s.replace("'", "''")

    def check_existing_work_item(self, title: str, repo_name: str, file_hint: str) -> bool:
        """
        Returns True if it's OK to create (no existing match). Returns False if a match exists.
        """
        title_q = self._escape_wiql(title)
        repo_q = self._escape_wiql(repo_name)
        hint_q = self._escape_wiql(file_hint)
        query = f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.WorkItemType] = 'Task'
          AND [System.Title] = '{title_q}'
          AND [Custom.Repository] = '{repo_q}'
          AND [System.Description] CONTAINS '{hint_q}'
          AND [Custom.TaskSource] = 'Semgrep'
        """
        r = self.sess.post(
            self._wiql_url(),
            headers={"Content-Type": "application/json"},
            json={"query": query},
            auth=self.auth,
            timeout=30,
        )
        if r.status_code != 200:
            logger.warning("WIQL query failed (%s): %s", r.status_code, r.text[:300])
            return True
        items = (r.json() or {}).get("workItems", []) or []
        return len(items) == 0

    def create_task_work_item(
        self,
        title: str,
        html_description: str,
        area_path: str,
        iteration_path: str,
        severity: str,
        tags: str,
        ticket_type: str,
        repo_name: str,
    ) -> bool:
        patch: List[Dict[str, Any]] = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.AssignedTo", "value": self.ctx.requested_for_email},
            {"op": "add", "path": "/fields/System.Tags", "value": tags},
            {"op": "add", "path": "/fields/System.AreaPath", "value": area_path},
            {"op": "add", "path": "/fields/System.IterationPath", "value": iteration_path},
            {"op": "add", "path": "/fields/Custom.TaskSeverity", "value": severity.capitalize()},
            {"op": "add", "path": "/fields/Custom.TaskSource", "value": "Semgrep"},
            {"op": "add", "path": "/fields/Custom.Repository", "value": repo_name},
            {"op": "add", "path": "/fields/Custom.TicketType", "value": ticket_type},
            {"op": "add", "path": "/fields/System.Description", "value": html_description},
        ]

        if not area_path or not iteration_path:
            logger.error(
                "Cannot create work item %r — missing area (%r) or iteration (%r)",
                title,
                area_path or "(empty)",
                iteration_path or "(empty)",
            )
            return False

        if _env_bool("TICKET_CREATION_DRY_RUN", False):
            logger.info("[DRY RUN] Would create work item: %s", title)
            return True

        # Link PR if available
        pr_id = (self.ctx.pr_id or "").strip()
        if pr_id and pr_id != "0":
            patch.append(
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": "ArtifactLink",
                        "url": f"vstfs:///Git/PullRequestId/{self.ctx.project_id}/{self.ctx.repo_id}/{pr_id}",
                        "attributes": {"name": "pull request"},
                    },
                }
            )

        r = self.sess.post(
            self._wi_url(),
            headers={"Content-Type": "application/json-patch+json"},
            params={"api-version": "7.0"},
            json=patch,
            auth=self.auth,
            timeout=30,
        )
        if r.status_code == 200:
            wi_id = (r.json() or {}).get("id")
            logger.info("Created work item #%s: %s", wi_id, title)
            return True
        logger.error("Work item create failed (%s): %s", r.status_code, r.text[:500])
        return False


class SemgrepClient:
    def __init__(self):
        token = os.getenv("SEMGREP_APP_TOKEN", "").strip()
        if not token:
            raise RuntimeError("SEMGREP_APP_TOKEN missing")
        self.token = token
        self.deployment_id = os.getenv("DEPLOYMENT_ID", os.getenv("deploymentId", "")).strip()
        self.sess = _requests_session()
        self.sess.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            }
        )
        self.deployment_slug = self.get_deployment_slug()

    def get_deployment_slug(self) -> str:
        r = self.sess.get("https://semgrep.dev/api/v1/deployments", timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Failed to fetch deployments: {r.status_code} {r.text[:300]}")
        data = r.json()
        slug = (data.get("deployments") or [{}])[0].get("slug")
        if not slug:
            raise RuntimeError("Could not determine deployment slug from /deployments")
        return slug

    def list_findings(
        self,
        deployment_slug: str,
        issue_type: str,
        repo_name: str,
        ref: Optional[str],
        severities: Sequence[str],
        confidence: Optional[str] = None,
        exposures: Sequence[str] = (),
        transitivities: Sequence[str] = (),
        page_size: int = 100,
        max_pages: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Uses: GET /api/v1/deployments/{deploymentSlug}/findings
        Returns merged list from response {sastFindings|scaFindings}.findings
        """
        page_size = max(100, min(page_size, 3000))
        findings: List[Dict[str, Any]] = []
        base = f"https://semgrep.dev/api/v1/deployments/{deployment_slug}/findings"
        issue_type = issue_type.lower()
        for page in range(0, max_pages):
            params: List[Tuple[str, str]] = [
                ("issue_type", issue_type),
                ("dedup", "true"),
                ("page", str(page)),
                ("page_size", str(page_size)),
            ]
            if repo_name:
                params.append(("repos", repo_name))
            if ref:
                params.append(("ref", ref))
            for s in severities:
                params.append(("severities", _normalize_choice(s)))
            if confidence:
                params.append(("confidence", _normalize_choice(confidence)))
            for e in exposures:
                params.append(("exposures", e))
            for t in transitivities:
                params.append(("transitivities", t))

            r = self.sess.get(base, params=params, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"Findings API failed: {r.status_code} {r.text[:300]}")
            data = r.json() or {}
            page_findings = extract_semgrep_findings(data, issue_type)
            if not page_findings:
                break
            findings.extend(page_findings)
            if len(page_findings) < page_size:
                break
        logger.info(
            "Semgrep API returned %d %s finding(s) for repo=%r ref=%r",
            len(findings),
            issue_type.upper(),
            repo_name,
            ref,
        )
        return findings

    # --- SBOM export (license) ---
    def request_sbom_export(self, repo_id: str, ref: Optional[str]) -> str:
        url = f"https://semgrep.dev/api/v1/deployments/{self.deployment_slug}/sbom/export"
        payload: Dict[str, Any] = {"repositoryId": str(repo_id)}
        if ref:
            payload["ref"] = ref
        r = self.sess.post(url, json=payload, timeout=60)
        if r.status_code not in (200, 202):
            raise RuntimeError(f"SBOM export request failed: {r.status_code} {r.text[:300]}")
        token = (r.json() or {}).get("taskToken")
        if not token:
            raise RuntimeError(f"SBOM export missing taskToken: {r.text[:300]}")
        return token

    def poll_sbom_export_url(self, task_token: str, timeout_s: int = 180) -> str:
        url = f"https://semgrep.dev/api/v1/deployments/{self.deployment_slug}/sbom/export/{task_token}"
        start = time.time()
        while time.time() - start < timeout_s:
            r = self.sess.get(url, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"SBOM export poll failed: {r.status_code} {r.text[:300]}")
            data = r.json() or {}
            if data.get("status") == "SBOM_EXPORT_STATUS_COMPLETED":
                download_url = data.get("downloadUrl")
                if not download_url:
                    raise RuntimeError("SBOM export completed but downloadUrl missing")
                return download_url
            time.sleep(3)
        raise RuntimeError(f"SBOM export timed out after {timeout_s}s")

    def download_json(self, url: str) -> Dict[str, Any]:
        r = self.sess.get(url, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Download failed: {r.status_code} {r.text[:300]}")
        return r.json()


def _reachability_to_filters(values: Sequence[str]) -> Tuple[List[str], List[str]]:
    """
    Our UI mixes reachability + transitivity in one multiSelect.
    Map to Semgrep API query params:
      exposures: reachable, always_reachable, conditionally_reachable, unreachable, unknown
      transitivities: direct, transitive, unknown
    """
    exposures: List[str] = []
    transitivities: List[str] = []
    for v in values:
        n = _normalize_choice(v)
        if n in ("always_reachable", "always-reachable", "alwaysreachable"):
            exposures.append("always_reachable")
        elif n in ("reachable",):
            exposures.append("reachable")
        elif n in ("conditionally_reachable", "conditionally-reachable"):
            exposures.append("conditionally_reachable")
        elif n in ("unreachable",):
            exposures.append("unreachable")
        elif n in ("unknown",):
            exposures.append("unknown")
        elif n in ("direct",):
            transitivities.append("direct")
        elif n in ("transitive",):
            transitivities.append("transitive")
    # de-dupe
    exposures = sorted(set(exposures))
    transitivities = sorted(set(transitivities))
    return exposures, transitivities


def _should_create_by_time(pipeline_start: Optional[datetime], relevant_since: Optional[datetime]) -> bool:
    scan_type = os.getenv("SCAN_TYPE", "").strip().lower()
    if scan_type == "full scan":
        return True
    if pipeline_start is None or relevant_since is None:
        return True
    return relevant_since > pipeline_start


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _build_code_url(repo_uri: str, branch: str, loc: Dict[str, Any]) -> str:
    # Matches your prior scripts’ link format
    file_path = loc.get("filePath") or loc.get("file_path") or ""
    line = loc.get("line") or 1
    end_line = loc.get("endLine") or loc.get("end_line") or line
    col = loc.get("column") or loc.get("startColumn") or loc.get("column") or 1
    end_col = loc.get("endColumn") or loc.get("end_column") or col
    return (
        f"{repo_uri}"
        f"?path=/{file_path}"
        f"&version=GB{branch}"
        f"&line={line}"
        f"&lineEnd={end_line}"
        f"&lineStartColumn={col}"
        f"&lineEndColumn={end_col}"
        f"&lineStyle=plain&_a=contents"
    )


def _html_description(
    summary: str,
    body: str,
    semgrep_url: str,
    severity: str,
    extra_links_html: str = "",
) -> str:
    return (
        "<!DOCTYPE html><html><body>"
        f"<p><strong>Summary:</strong> {_html_escape(summary)}</p>"
        f"<p>{body}</p>"
        f"{extra_links_html}"
        f"<p><strong>Link to Semgrep:</strong> <a href=\"{_html_escape(semgrep_url)}\">{_html_escape(semgrep_url)}</a></p>"
        f"<p><strong>Severity:</strong> {_html_escape(severity)}</p>"
        "</body></html>"
    )


def _parse_ticket_types(raw: str) -> Set[str]:
    vals = {_normalize_choice(x) for x in _split_csvish(raw)}
    if not vals or "all" in vals:
        return {"sast", "sca", "license"}
    out: Set[str] = set()
    for v in vals:
        if v in ("sast", "source_code", "sourcecode"):
            out.add("sast")
        if v in ("sca", "supply_chain", "supplychain"):
            out.add("sca")
        if v in ("license", "licenses"):
            out.add("license")
    return out


def _license_whitelist() -> Set[str]:
    use_default = _env_bool("USE_DEFAULT_LICENSE_WHITELIST", True)
    override = set(_split_csvish(os.getenv("LICENSE_WHITELIST_OVERRIDE", "")))
    if use_default:
        # Default + additions
        return set(DEFAULT_APPROVED_LICENSES) | override
    # Override becomes complete list
    return override


def _get_ado_context() -> AdoContext:
    return AdoContext(
        collection_uri=os.getenv("SYSTEM_COLLECTIONURI", ""),
        project_id=os.getenv("SYSTEM_TEAMPROJECTID", ""),
        repo_id=os.getenv("BUILD_REPOSITORY_ID", ""),
        repo_uri=os.getenv("BUILD_REPOSITORY_URI", ""),
        repo_name=os.getenv("BUILD_REPOSITORY_NAME", ""),
        requested_for_email=os.getenv("BUILD_REQUESTEDFOREMAIL", ""),
        pr_id=os.getenv("SYSTEM_PULLREQUEST_PULLREQUESTID", "0"),
        source_branch_name=os.getenv("BUILD_SOURCEBRANCHNAME", os.getenv("BUILD_SOURCEBRANCHNAME", "")),
        pipeline_start=_parse_pipeline_time(),
    )


def create_sast_tickets(
    ado: AzureDevOpsClient,
    semgrep: SemgrepClient,
    slug: str,
    semgrep_repo: str,
    area: str,
    iteration: str,
    branch_ref: Optional[str],
    findings_json_path: str,
) -> int:
    repo = ado.ctx.repo_name
    branch = ado.ctx.source_branch_name or "master"

    severities = _split_csvish(os.getenv("SAST_SEVERITIES", "Critical,High"))
    confidences = _split_csvish(os.getenv("SAST_CONFIDENCES", "High,Medium"))
    allowed_conf = {_normalize_choice(c) for c in confidences} if confidences else set()
    allowed_sev = {_normalize_choice(s) for s in severities} if severities else set()

    findings = _load_findings_from_cli_json(findings_json_path, "sast")
    if not findings:
        findings = semgrep.list_findings(
            deployment_slug=slug,
            issue_type="sast",
            repo_name=semgrep_repo,
            ref=branch_ref,
            severities=severities or ["critical", "high", "medium", "low"],
            confidence=None,
            page_size=200,
            max_pages=20,
        )

    grouped: Dict[str, Dict[str, Any]] = {}
    created = 0

    for f in findings:
        sev = _normalize_choice(str(f.get("severity") or ""))
        conf = _normalize_choice(str(f.get("confidence") or (f.get("rule") or {}).get("confidence") or ""))
        if allowed_sev and sev not in allowed_sev:
            continue
        if allowed_conf and conf not in allowed_conf:
            continue

        relevant_since = _parse_relevant_since(str(f.get("relevant_since") or ""))
        if not _should_create_by_time(ado.ctx.pipeline_start, relevant_since):
            continue

        title = str((f.get("rule") or {}).get("name") or f.get("rule_name") or "Semgrep finding")
        rule_msg = str((f.get("rule") or {}).get("message") or f.get("rule_message") or "")
        loc = f.get("location") or {}
        file_info = f"{loc.get('filePath') or loc.get('file_path') or ''}:{loc.get('line') or loc.get('line') or ''}"
        code_url = _build_code_url(ado.ctx.repo_uri, branch, loc)
        finding_id = f.get("id")
        finding_url = f"https://semgrep.dev/orgs/{slug}/findings/{finding_id}" if finding_id else ""
        semgrep_repo_url = f"https://semgrep.dev/orgs/{slug}/findings?repo={repo}&ref={branch}"

        # De-dupe / group by title
        if title not in grouped:
            grouped[title] = {
                "title": title,
                "msg": rule_msg,
                "severity": sev,
                "semgrep_url": semgrep_repo_url,
                "links": [],
                "hint": file_info or title,
            }
        grouped[title]["links"].append((file_info, code_url, finding_url))

    for title, g in grouped.items():
        # existing check uses first file hint
        hint = str(g.get("hint") or title)
        if not ado.check_existing_work_item(title, ado.ctx.repo_name, hint):
            continue

        links_html = "<p><strong>Locations:</strong></p>"
        for (fi, cu, fu) in g["links"]:
            loc_html = f"<p><a href=\"{_html_escape(cu)}\">{_html_escape(fi)}</a>"
            if fu:
                loc_html += f" — <a href=\"{_html_escape(fu)}\">Semgrep finding</a>"
            loc_html += "</p>"
            links_html += loc_html

        body = _html_escape(g.get("msg") or "")
        desc = _html_description(
            summary=title,
            body=body,
            semgrep_url=str(g.get("semgrep_url") or ""),
            severity=str(g.get("severity") or ""),
            extra_links_html=links_html,
        )
        ok = ado.create_task_work_item(
            title=title,
            html_description=desc,
            area_path=area,
            iteration_path=iteration,
            severity=str(g.get("severity") or "medium"),
            tags="semgrep;SAST",
            ticket_type="Source Code",
            repo_name=ado.ctx.repo_name,
        )
        if ok:
            created += 1

    return created


def create_sca_tickets(
    ado: AzureDevOpsClient,
    semgrep: SemgrepClient,
    slug: str,
    semgrep_repo: str,
    area: str,
    iteration: str,
    branch_ref: Optional[str],
    findings_json_path: str,
) -> int:
    repo = ado.ctx.repo_name
    branch = ado.ctx.source_branch_name or "master"

    severities = _split_csvish(os.getenv("SCA_SEVERITIES", "Critical,High"))
    reach = _split_csvish(os.getenv("SCA_REACHABILITIES", "Always Reachable,Reachable,Direct"))
    exposures, transitivities = _reachability_to_filters(reach)

    findings = _load_findings_from_cli_json(findings_json_path, "sca")
    if not findings:
        findings = semgrep.list_findings(
            deployment_slug=slug,
            issue_type="sca",
            repo_name=semgrep_repo,
            ref=branch_ref,
            severities=severities or ["critical", "high", "medium", "low"],
            confidence=None,
            exposures=exposures,
            transitivities=transitivities,
            page_size=200,
            max_pages=20,
        )

    grouped: Dict[str, Dict[str, Any]] = {}
    created = 0

    for f in findings:
        sev = _normalize_choice(str(f.get("severity") or ""))
        relevant_since = _parse_relevant_since(str(f.get("relevant_since") or ""))
        if not _should_create_by_time(ado.ctx.pipeline_start, relevant_since):
            continue

        title = str((f.get("rule") or {}).get("name") or f.get("rule_name") or "Semgrep SCA finding")
        rule_msg = str((f.get("rule") or {}).get("message") or f.get("rule_message") or "")
        loc = f.get("location") or {}
        file_info = f"{loc.get('filePath') or loc.get('file_path') or ''}:{loc.get('line') or ''}"
        code_url = _build_code_url(ado.ctx.repo_uri, branch, loc)
        finding_id = f.get("id")
        finding_url = f"https://semgrep.dev/orgs/{slug}/findings/{finding_id}" if finding_id else ""
        semgrep_repo_url = f"https://semgrep.dev/orgs/{slug}/supply-chain/vulnerabilities?repo={repo}&ref={branch}"

        if title not in grouped:
            grouped[title] = {
                "title": title,
                "msg": rule_msg,
                "severity": sev,
                "semgrep_url": semgrep_repo_url,
                "links": [],
                "hint": file_info or title,
                "fix": f.get("fix_recommendations") or [],
                "reachability": f.get("reachability") or "",
            }
        grouped[title]["links"].append((file_info, code_url, finding_url))

    for title, g in grouped.items():
        hint = str(g.get("hint") or title)
        if not ado.check_existing_work_item(title, ado.ctx.repo_name, hint):
            continue

        links_html = "<p><strong>Locations:</strong></p>"
        for (fi, cu, fu) in g["links"]:
            loc_html = f"<p><a href=\"{_html_escape(cu)}\">{_html_escape(fi)}</a>"
            if fu:
                loc_html += f" — <a href=\"{_html_escape(fu)}\">Semgrep finding</a>"
            loc_html += "</p>"
            links_html += loc_html

        extra = ""
        reachability = str(g.get("reachability") or "")
        if reachability:
            extra += f"<p><strong>Reachability:</strong> {_html_escape(reachability)}</p>"
        fix_recs = g.get("fix") or []
        if isinstance(fix_recs, list) and fix_recs:
            extra += "<p><strong>Fix recommendations:</strong></p>"
            for fr in fix_recs[:10]:
                pkg = fr.get("package") if isinstance(fr, dict) else None
                ver = fr.get("version") if isinstance(fr, dict) else None
                if pkg or ver:
                    extra += f"<p>- {_html_escape(str(pkg or ''))} {_html_escape(str(ver or ''))}</p>"

        body = _html_escape(g.get("msg") or "")
        desc = _html_description(
            summary=title,
            body=body + extra,
            semgrep_url=str(g.get("semgrep_url") or ""),
            severity=str(g.get("severity") or ""),
            extra_links_html=links_html,
        )
        ok = ado.create_task_work_item(
            title=title,
            html_description=desc,
            area_path=area,
            iteration_path=iteration,
            severity=str(g.get("severity") or "medium"),
            tags="semgrep;SCA",
            ticket_type="Vulnerable library",
            repo_name=ado.ctx.repo_name,
        )
        if ok:
            created += 1
    return created


def create_license_tickets(
    ado: AzureDevOpsClient,
    semgrep: SemgrepClient,
    slug: str,
    semgrep_repo: str,
    area: str,
    iteration: str,
) -> int:
    repo_name = ado.ctx.repo_name
    branch = ado.ctx.source_branch_name or "master"

    whitelist = _license_whitelist()
    if not whitelist:
        logger.warning("License whitelist is empty; skipping license ticket creation.")
        return 0

    proj_url = f"https://semgrep.dev/api/v1/deployments/{slug}/projects/{semgrep_repo}"
    r = semgrep.sess.get(proj_url, timeout=60)
    if r.status_code != 200:
        logger.warning("Could not fetch Semgrep project info for license check (%s): %s", r.status_code, r.text[:300])
        return 0
    proj = (r.json() or {}).get("project") or {}
    semgrep_repo_id = proj.get("id")
    if not semgrep_repo_id:
        logger.warning("Semgrep project info missing 'id' for %s; skipping license check.", repo_name)
        return 0

    # Request SBOM export and download
    task_token = semgrep.request_sbom_export(repo_id=str(semgrep_repo_id), ref=branch)
    dl_url = semgrep.poll_sbom_export_url(task_token)
    sbom = semgrep.download_json(dl_url)

    non_compliant: List[Dict[str, str]] = []
    for comp in sbom.get("components", []) or []:
        name = comp.get("name") or "Unknown"
        ver = comp.get("version") or "Unknown"
        for lic in comp.get("licenses", []) or []:
            lic_obj = (lic or {}).get("license") or {}
            lic_name = (lic_obj.get("name") or lic_obj.get("id") or "Unknown").strip()
            lic_id = (lic_obj.get("id") or "").strip()
            ok = (lic_id in whitelist) or (lic_name in whitelist)
            if not ok:
                non_compliant.append({"component": name, "version": ver, "license": lic_name or lic_id or "Unknown"})

    created = 0
    for issue in non_compliant:
        title = f"Non-compliant license in {issue['component']} {issue['version']}"
        hint = f"{issue['component']}@{issue['version']}"
        if not ado.check_existing_work_item(title, ado.ctx.repo_name, hint):
            continue

        semgrep_url = f"https://semgrep.dev/orgs/{slug}/supply-chain/vulnerabilities?repo={semgrep_repo}&ref={branch}"
        body = _html_escape(
            f"Component {issue['component']} (version {issue['version']}) uses non-compliant license: {issue['license']}. "
            "Please review and replace or seek legal approval."
        )
        desc = _html_description(
            summary=title,
            body=body,
            semgrep_url=semgrep_url,
            severity="medium",
            extra_links_html=f"<p><strong>Component:</strong> {_html_escape(hint)}</p>",
        )
        ok = ado.create_task_work_item(
            title=title,
            html_description=desc,
            area_path=area,
            iteration_path=iteration,
            severity="medium",
            tags="semgrep;SCA;License;Compliance",
            ticket_type="License Compliance",
            repo_name=ado.ctx.repo_name,
        )
        if ok:
            created += 1
    return created


def main() -> int:
    if not _env_bool("ENABLE_TICKET_CREATION", False):
        logger.info("Ticket creation disabled (ENABLE_TICKET_CREATION=false).")
        return 0

    ctx = _get_ado_context()
    missing = [k for k, v in [("SYSTEM_COLLECTIONURI", ctx.collection_uri), ("SYSTEM_TEAMPROJECTID", ctx.project_id), ("BUILD_REPOSITORY_ID", ctx.repo_id)] if not v]
    if missing:
        raise RuntimeError(f"Missing required Azure DevOps env vars: {', '.join(missing)}")

    types = _parse_ticket_types(os.getenv("TICKET_TYPES", "All"))
    logger.info("Ticket types enabled: %s", ", ".join(sorted(types)))

    # Download CSV configs (optional)
    iter_url = os.getenv("ITERATION_LIST_CSV_URL", "").strip()
    area_url = os.getenv("AZURE_DEV_PATH_CSV_URL", "").strip()
    default_iteration = os.getenv("DEFAULT_ITERATION_PATH", "").strip()
    default_area = os.getenv("DEFAULT_AREA_PATH", "").strip()

    tmp_iter = "iterationlist.csv"
    tmp_area = "azuredevpath.csv"
    auth = _ado_auth()
    if iter_url:
        _download_to_file(iter_url, tmp_iter, auth=auth)
    if area_url:
        _download_to_file(area_url, tmp_area, auth=auth)

    sess = _requests_session()
    iteration_path = _resolve_iteration_path(sess, auth, default_iteration, tmp_iter)
    area_path = _normalize_ado_path(
        _area_path(tmp_area, ctx.requested_for_email, default_area) if os.path.exists(tmp_area) else default_area
    )

    org = _resolve_ado_org()
    project = _resolve_ado_project()
    if not area_path and org and project:
        area_path = _fetch_default_area_path(sess, org, project, auth)

    logger.info("Using AreaPath=%s", area_path or "(not configured)")
    logger.info("Using IterationPath=%s", iteration_path or "(not configured)")
    if not area_path or not iteration_path:
        logger.warning(
            "Area path or iteration path is not configured. Set defaultAreaPath/defaultIterationPath "
            "and adoTeam (e.g. 'Engineering Team') in pipeline inputs."
        )

    ado = AzureDevOpsClient(ctx)
    semgrep = SemgrepClient()
    slug = semgrep.deployment_slug
    semgrep_repo = resolve_semgrep_repo_name(
        semgrep.sess,
        semgrep.token,
        slug,
        org,
        project,
        ctx.repo_name,
    )
    branch_ref = git_branch_ref(ctx.source_branch_name)
    findings_json_path = os.getenv("FINDINGS_JSON_PATH", "").strip()

    total_created = 0
    if "sast" in types:
        total_created += create_sast_tickets(
            ado, semgrep, slug, semgrep_repo, area_path, iteration_path, branch_ref, findings_json_path
        )
    if "sca" in types:
        total_created += create_sca_tickets(
            ado, semgrep, slug, semgrep_repo, area_path, iteration_path, branch_ref, findings_json_path
        )
    if "license" in types:
        try:
            total_created += create_license_tickets(ado, semgrep, slug, semgrep_repo, area_path, iteration_path)
        except Exception as e:
            logger.warning("License ticket creation skipped: %s", e)

    logger.info("Total work items created: %s", total_created)
    print(f"TOTAL_WORK_ITEMS_CREATED={total_created}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        logger.error("Ticket creation failed: %s", e, exc_info=True)
        raise

