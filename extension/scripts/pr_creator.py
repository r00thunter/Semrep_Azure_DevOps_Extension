#!/usr/bin/env python3
"""
Semgrep Auto-Fix PR Creator

Creates pull requests with auto-fixes for Semgrep findings that have autofix code available.
Groups fixes by rule type (SAST, SCA) when configured.

Configuration via environment variables:
- SEMGREP_APP_TOKEN, DEPLOYMENT_ID
- CREATE_FIX_PR, FIX_PR_BRANCH_PREFIX, GROUP_FIX_PRS_BY_TYPE
- BUILD_REPOSITORY_NAME, BUILD_SOURCEBRANCHNAME
- SYSTEM_ACCESSTOKEN, SYSTEM_COLLECTIONURI, SYSTEM_TEAMPROJECTID, BUILD_REPOSITORY_ID
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests


def _log_level() -> int:
    lvl = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    return getattr(logging, lvl, logging.INFO)


logging.basicConfig(level=_log_level(), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pr_creator")


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if not v:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _requests_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({"User-Agent": "semgrep-ado-ext/1.0"})
    return sess


def _ado_auth() -> Tuple[str, str]:
    token = os.getenv("SYSTEM_ACCESSTOKEN", "")
    if not token:
        raise RuntimeError("SYSTEM_ACCESSTOKEN is missing. Enable 'Allow scripts to access OAuth token'.")
    return ("", token)


def get_deployment_slug(session: requests.Session, token: str) -> str:
    """Get deployment slug from Semgrep API"""
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    url = "https://semgrep.dev/api/v1/deployments"
    
    try:
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        deployments = data.get("deployments", [])
        if not deployments:
            raise RuntimeError("No deployments found in Semgrep account")
        slug = deployments[0].get("slug")
        if not slug:
            raise RuntimeError("Deployment slug not found in API response")
        logger.info(f"Using deployment slug: {slug}")
        return slug
    except requests.RequestException as e:
        logger.error(f"Failed to get deployment slug: {e}")
        raise


def get_findings_with_autofix(
    session: requests.Session,
    token: str,
    deployment_slug: str,
    repo_name: str,
    branch_name: str,
    issue_type: str = "sast"
) -> List[Dict[str, Any]]:
    """Fetch findings that have autofix code available"""
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    params = {
        "issue_type": issue_type,
        "repos": repo_name,
        "ref": f"refs/heads/{branch_name}" if branch_name else None,
        "dedup": "true",
        "page_size": 3000
    }
    
    params = {k: v for k, v in params.items() if v is not None}
    url = f"https://semgrep.dev/api/v1/deployments/{deployment_slug}/findings"
    
    all_findings = []
    page = 0
    
    try:
        while True:
            params["page"] = page
            resp = session.get(url, headers=headers, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            
            if issue_type == "sast":
                findings_data = data.get("sastFindings", {})
            else:
                findings_data = data.get("scaFindings", {})
            
            findings = findings_data.get("findings", [])
            if not findings:
                break
            
            # Filter findings that have autofix code
            for finding in findings:
                assistant = finding.get("assistant", {})
                autofix = assistant.get("autofix", {})
                fix_code = autofix.get("fix_code")
                
                # Check if PR already exists
                click_to_fix_prs = finding.get("click_to_fix_prs", [])
                if click_to_fix_prs:
                    logger.debug(f"Finding {finding.get('id')} already has PRs: {[pr.get('url') for pr in click_to_fix_prs]}")
                    continue
                
                if fix_code:
                    all_findings.append(finding)
            
            if len(findings) < params.get("page_size", 100):
                break
            
            page += 1
            
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {issue_type} findings: {e}")
        raise
    
    logger.info(f"Found {len(all_findings)} {issue_type} findings with autofix code (no existing PRs)")
    return all_findings


def get_file_content(
    session: requests.Session,
    auth: Tuple[str, str],
    collection_uri: str,
    project_id: str,
    repo_id: str,
    file_path: str,
    branch: str = "master"
) -> Optional[str]:
    """Get file content from Azure DevOps repository"""
    url = f"{collection_uri}{project_id}/_apis/git/repositories/{repo_id}/items"
    params = {
        "path": file_path,
        "versionDescriptor.version": branch,
        "versionDescriptor.versionType": "branch",
        "api-version": "7.0"
    }
    
    try:
        resp = session.get(url, params=params, auth=auth, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.warning(f"Failed to get file {file_path}: {e}")
        return None


def create_branch(
    session: requests.Session,
    auth: Tuple[str, str],
    collection_uri: str,
    project_id: str,
    repo_id: str,
    branch_name: str,
    source_branch: str = "master"
) -> bool:
    """Create a new branch in Azure DevOps repository"""
    url = f"{collection_uri}{project_id}/_apis/git/repositories/{repo_id}/refs"
    
    # First, get the source branch commit
    refs_url = f"{collection_uri}{project_id}/_apis/git/repositories/{repo_id}/refs"
    refs_params = {
        "filter": f"heads/{source_branch}",
        "api-version": "7.0"
    }
    
    try:
        resp = session.get(refs_url, params=refs_params, auth=auth, timeout=30)
        resp.raise_for_status()
        refs_data = resp.json()
        
        if not refs_data.get("value"):
            logger.error(f"Source branch {source_branch} not found")
            return False
        
        source_object_id = refs_data["value"][0]["objectId"]
        
        # Create new branch
        payload = [{
            "name": f"refs/heads/{branch_name}",
            "oldObjectId": "0000000000000000000000000000000000000000",
            "newObjectId": source_object_id
        }]
        
        create_resp = session.post(url, json=payload, auth=auth, params={"api-version": "7.0"}, timeout=30)
        create_resp.raise_for_status()
        
        logger.info(f"Created branch: {branch_name}")
        return True
        
    except requests.RequestException as e:
        logger.error(f"Failed to create branch {branch_name}: {e}")
        return False


def create_commit(
    session: requests.Session,
    auth: Tuple[str, str],
    collection_uri: str,
    project_id: str,
    repo_id: str,
    branch: str,
    file_changes: List[Dict[str, Any]],
    commit_message: str
) -> bool:
    """Create a commit with file changes"""
    url = f"{collection_uri}{project_id}/_apis/git/repositories/{repo_id}/pushes"
    
    # Get current branch commit
    refs_url = f"{collection_uri}{project_id}/_apis/git/repositories/{repo_id}/refs"
    refs_params = {
        "filter": f"heads/{branch}",
        "api-version": "7.0"
    }
    
    try:
        resp = session.get(refs_url, params=refs_params, auth=auth, timeout=30)
        resp.raise_for_status()
        refs_data = resp.json()
        
        if not refs_data.get("value"):
            logger.error(f"Branch {branch} not found")
            return False
        
        old_object_id = refs_data["value"][0]["objectId"]
        
        # Prepare push payload
        payload = {
            "refUpdates": [{
                "name": f"refs/heads/{branch}",
                "oldObjectId": old_object_id
            }],
            "commits": [{
                "comment": commit_message,
                "changes": file_changes
            }]
        }
        
        push_resp = session.post(url, json=payload, auth=auth, params={"api-version": "7.0"}, timeout=60)
        push_resp.raise_for_status()
        
        logger.info(f"Created commit on branch {branch}")
        return True
        
    except requests.RequestException as e:
        logger.error(f"Failed to create commit: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        return False


def create_pull_request(
    session: requests.Session,
    auth: Tuple[str, str],
    collection_uri: str,
    project_id: str,
    repo_id: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str
) -> Optional[str]:
    """Create a pull request in Azure DevOps"""
    url = f"{collection_uri}{project_id}/_apis/git/repositories/{repo_id}/pullrequests"
    
    payload = {
        "sourceRefName": f"refs/heads/{source_branch}",
        "targetRefName": f"refs/heads/{target_branch}",
        "title": title,
        "description": description
    }
    
    try:
        resp = session.post(url, json=payload, auth=auth, params={"api-version": "7.0"}, timeout=30)
        resp.raise_for_status()
        pr_data = resp.json()
        pr_url = pr_data.get("url", "")
        pr_id = pr_data.get("pullRequestId", "")
        
        logger.info(f"Created PR #{pr_id}: {pr_url}")
        return pr_url
        
    except requests.RequestException as e:
        logger.error(f"Failed to create PR: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        return None


def sanitize_branch_name(name: str) -> str:
    """Sanitize branch name to be valid for Git"""
    # Remove invalid characters
    name = re.sub(r'[^a-zA-Z0-9/._-]', '-', name)
    # Remove consecutive dashes
    name = re.sub(r'-+', '-', name)
    # Remove leading/trailing dashes
    name = name.strip('-')
    # Limit length
    if len(name) > 200:
        name = name[:200]
    return name


def group_findings_by_rule_type(findings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group findings by rule type (SAST or SCA)"""
    grouped = {"sast": [], "sca": []}
    
    for finding in findings:
        # Determine type based on presence of certain fields
        if finding.get("found_dependency") or finding.get("vulnerability_identifier"):
            grouped["sca"].append(finding)
        else:
            grouped["sast"].append(finding)
    
    return grouped


def apply_autofix_to_file(
    file_content: str,
    location: Dict[str, Any],
    fix_code: str
) -> Optional[str]:
    """Apply autofix code to file content"""
    if not file_content or not location:
        return None
    
    try:
        lines = file_content.split('\n')
        start_line = location.get("line", 1) - 1  # 0-indexed
        end_line = location.get("endLine", start_line + 1) - 1
        
        # Get the fix code lines
        fix_lines = fix_code.split('\n')
        
        # Replace the lines
        new_lines = lines[:start_line] + fix_lines + lines[end_line + 1:]
        
        return '\n'.join(new_lines)
        
    except Exception as e:
        logger.error(f"Failed to apply autofix: {e}")
        return None


def create_fix_prs_for_type(
    session: requests.Session,
    auth: Tuple[str, str],
    collection_uri: str,
    project_id: str,
    repo_id: str,
    repo_name: str,
    deployment_slug: str,
    findings: List[Dict[str, Any]],
    rule_type: str,
    branch_prefix: str,
    target_branch: str
) -> List[str]:
    """Create PRs for findings of a specific type"""
    if not findings:
        return []
    
    created_prs = []
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    branch_name = sanitize_branch_name(f"{branch_prefix}{rule_type}-{timestamp}")
    
    logger.info(f"Creating PR for {len(findings)} {rule_type.upper()} findings on branch: {branch_name}")
    
    # Create branch
    if not create_branch(session, auth, collection_uri, project_id, repo_id, branch_name, target_branch):
        logger.error(f"Failed to create branch {branch_name}")
        return []
    
    # Group findings by file
    findings_by_file: Dict[str, List[Dict[str, Any]]] = {}
    for finding in findings:
        location = finding.get("location", {})
        file_path = location.get("filePath", "")
        if file_path:
            if file_path not in findings_by_file:
                findings_by_file[file_path] = []
            findings_by_file[file_path].append(finding)
    
    # Get current file contents and apply fixes
    file_changes = []
    pr_description_parts = [
        f"## Auto-Fix PR for {rule_type.upper()} Findings",
        f"\nThis PR contains auto-fixes for {len(findings)} Semgrep findings.\n",
        "### Findings Fixed:\n"
    ]
    
    for file_path, file_findings in findings_by_file.items():
        # Get current file content
        file_content = get_file_content(session, auth, collection_uri, project_id, repo_id, file_path, target_branch)
        if not file_content:
            logger.warning(f"Could not get file content for {file_path}, skipping")
            continue
        
        # Apply all fixes for this file
        modified_content = file_content
        for finding in file_findings:
            assistant = finding.get("assistant", {})
            autofix = assistant.get("autofix", {})
            fix_code = autofix.get("fix_code", "")
            location = finding.get("location", {})
            
            if fix_code and location:
                modified_content = apply_autofix_to_file(modified_content, location, fix_code)
                
                # Add to PR description
                rule = finding.get("rule", {})
                rule_name = rule.get("name", "Unknown rule")
                finding_id = finding.get("id", "")
                finding_url = f"https://semgrep.dev/orgs/{deployment_slug}/findings/{finding_id}"
                
                pr_description_parts.append(f"- **{rule_name}** in `{file_path}:{location.get('line')}` - [View Finding]({finding_url})")
        
        if modified_content != file_content:
            # Encode file content
            encoded_content = base64.b64encode(modified_content.encode('utf-8')).decode('utf-8')
            
            file_changes.append({
                "changeType": "edit",
                "item": {
                    "path": file_path
                },
                "newContent": {
                    "content": encoded_content,
                    "contentType": "base64Encoded"
                }
            })
    
    if not file_changes:
        logger.warning("No file changes to commit")
        return []
    
    # Create commit
    commit_message = f"Auto-fix {len(findings)} {rule_type.upper()} findings from Semgrep"
    if not create_commit(session, auth, collection_uri, project_id, repo_id, branch_name, file_changes, commit_message):
        logger.error("Failed to create commit")
        return []
    
    # Create PR
    pr_title = f"Auto-fix: {len(findings)} {rule_type.upper()} findings"
    pr_description = "\n".join(pr_description_parts)
    pr_description += f"\n\n---\n*This PR was automatically created by Semgrep Azure DevOps Extension*"
    
    pr_url = create_pull_request(
        session, auth, collection_uri, project_id, repo_id,
        branch_name, target_branch, pr_title, pr_description
    )
    
    if pr_url:
        created_prs.append(pr_url)
        logger.info(f"✅ Created PR: {pr_url}")
    else:
        logger.error("Failed to create PR")
    
    return created_prs


def main():
    """Main execution function"""
    try:
        # Check if PR creation is enabled
        if not _env_bool("CREATE_FIX_PR", False):
            logger.info("PR creation is disabled. Skipping.")
            sys.exit(0)
        
        # Get configuration
        token = os.getenv("SEMGREP_APP_TOKEN", "")
        if not token:
            logger.error("SEMGREP_APP_TOKEN is not set")
            sys.exit(1)
        
        deployment_id = os.getenv("DEPLOYMENT_ID", "15145")
        repo_name = os.getenv("BUILD_REPOSITORY_NAME", "")
        branch_name = os.getenv("BUILD_SOURCEBRANCHNAME", "")
        branch_prefix = os.getenv("FIX_PR_BRANCH_PREFIX", "semgrep-fixes/")
        group_by_type = _env_bool("GROUP_FIX_PRS_BY_TYPE", True)
        
        # Azure DevOps variables
        collection_uri = os.getenv("SYSTEM_COLLECTIONURI", "")
        project_id = os.getenv("SYSTEM_TEAMPROJECTID", "")
        repo_id = os.getenv("BUILD_REPOSITORY_ID", "")
        
        if not all([repo_name, collection_uri, project_id, repo_id]):
            logger.error("Missing required Azure DevOps environment variables")
            sys.exit(1)
        
        # Determine target branch (usually master/main)
        target_branch = "master"
        if branch_name and branch_name not in ["master", "main"]:
            # For PR builds, target the base branch
            target_branch = "master"  # Default, could be enhanced to detect base branch
        
        logger.info(f"Creating fix PRs for {repo_name} (source: {branch_name}, target: {target_branch})")
        
        # Create session and auth
        session = _requests_session()
        auth = _ado_auth()
        
        # Get deployment slug
        deployment_slug = get_deployment_slug(session, token)
        
        # Get findings with autofix
        logger.info("Fetching SAST findings with autofix...")
        sast_findings = get_findings_with_autofix(session, token, deployment_slug, repo_name, branch_name, "sast")
        
        logger.info("Fetching SCA findings with autofix...")
        sca_findings = get_findings_with_autofix(session, token, deployment_slug, repo_name, branch_name, "sca")
        
        all_findings = sast_findings + sca_findings
        
        if not all_findings:
            logger.info("No findings with autofix code available (or all already have PRs)")
            sys.exit(0)
        
        logger.info(f"Found {len(all_findings)} total findings with autofix code")
        
        created_prs = []
        
        if group_by_type:
            # Group by type and create one PR per type
            grouped = group_findings_by_rule_type(all_findings)
            
            for rule_type, findings in grouped.items():
                if findings:
                    prs = create_fix_prs_for_type(
                        session, auth, collection_uri, project_id, repo_id,
                        repo_name, deployment_slug, findings, rule_type,
                        branch_prefix, target_branch
                    )
                    created_prs.extend(prs)
        else:
            # Create one PR per finding (not recommended for many findings)
            logger.warning("Creating individual PRs per finding (groupFixPRsByType=false). This may create many PRs.")
            # For now, still group by type to avoid creating too many PRs
            grouped = group_findings_by_rule_type(all_findings)
            for rule_type, findings in grouped.items():
                if findings:
                    prs = create_fix_prs_for_type(
                        session, auth, collection_uri, project_id, repo_id,
                        repo_name, deployment_slug, findings, rule_type,
                        branch_prefix, target_branch
                    )
                    created_prs.extend(prs)
        
        if created_prs:
            logger.info(f"✅ Successfully created {len(created_prs)} PR(s):")
            for pr_url in created_prs:
                logger.info(f"  - {pr_url}")
        else:
            logger.warning("No PRs were created")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"PR creation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
