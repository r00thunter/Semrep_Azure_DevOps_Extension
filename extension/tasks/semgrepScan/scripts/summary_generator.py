#!/usr/bin/env python3
"""
Semgrep Summary Generator

Generates comprehensive summary reports with vulnerability details, code samples,
and fix suggestions. Outputs in both markdown (for pipeline logs) and test results
format (for Azure DevOps tab view).

Configuration via environment variables:
- SEMGREP_APP_TOKEN, DEPLOYMENT_ID
- GENERATE_SUMMARY, SUMMARY_DISPLAY_MODE
- BUILD_REPOSITORY_NAME, BUILD_SOURCEBRANCHNAME
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# Import shared utilities
try:
    from api_utils import DeploymentSlugCache, retry_with_backoff, handle_partial_failures
    from metrics import get_metrics_collector
except ImportError:
    # Fallback if utilities not available
    DeploymentSlugCache = None
    retry_with_backoff = lambda *args, **kwargs: lambda f: f
    handle_partial_failures = None
    get_metrics_collector = lambda: None


def _log_level() -> int:
    lvl = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    return getattr(logging, lvl, logging.INFO)


logging.basicConfig(level=_log_level(), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("summary_generator")


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if not v:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _requests_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({"User-Agent": "semgrep-ado-ext/1.0"})
    return sess


def get_deployment_slug(session: requests.Session, token: str) -> str:
    """Get deployment slug from Semgrep API (with caching)"""
    if DeploymentSlugCache:
        return DeploymentSlugCache.get(session, token)
    
    # Fallback to direct API call
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    url = "https://semgrep.dev/api/v1/deployments"
    
    @retry_with_backoff(max_retries=3)
    def fetch_slug():
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp
    
    try:
        resp = fetch_slug()
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


def get_findings(
    session: requests.Session,
    token: str,
    deployment_slug: str,
    repo_name: str,
    branch_name: str,
    issue_type: str = "sast"
) -> List[Dict[str, Any]]:
    """
    Fetch findings from Semgrep API with full details including assistant data
    Uses retry logic and handles rate limits
    """
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Build query parameters
    params = {
        "issue_type": issue_type,
        "repos": repo_name,
        "ref": f"refs/heads/{branch_name}" if branch_name else None,
        "dedup": "true",
        "page_size": 3000  # Get as many as possible
    }
    
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}
    
    url = f"https://semgrep.dev/api/v1/deployments/{deployment_slug}/findings"
    
    all_findings = []
    page = 0
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def fetch_page(page_num: int):
        page_params = params.copy()
        page_params["page"] = page_num
        logger.debug(f"Fetching {issue_type} findings, page {page_num}...")
        resp = session.get(url, headers=headers, params=page_params, timeout=60)
        resp.raise_for_status()
        return resp
    
    try:
        while True:
            resp = fetch_page(page)
            data = resp.json()
            
            # Extract findings based on issue type
            if issue_type == "sast":
                findings_data = data.get("sastFindings", {})
            else:
                findings_data = data.get("scaFindings", {})
            
            findings = findings_data.get("findings", [])
            if not findings:
                break
            
            all_findings.extend(findings)
            logger.info(f"Retrieved {len(findings)} {issue_type} findings from page {page}")
            
            # Check if there are more pages
            if len(findings) < params.get("page_size", 100):
                break
            
            page += 1
            # Small delay between pages to avoid rate limits
            time.sleep(0.5)
            
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {issue_type} findings: {e}")
        if hasattr(e, 'response') and e.response and e.response.status_code == 401:
            raise RuntimeError("Authentication failed. Check SEMGREP_APP_TOKEN.")
        raise
    
    logger.info(f"Total {issue_type} findings retrieved: {len(all_findings)}")
    return all_findings


def format_code_location(location: Dict[str, Any]) -> str:
    """Format code location for display"""
    if not location:
        return "Unknown location"
    
    file_path = location.get("filePath", "unknown")
    line = location.get("line", 0)
    end_line = location.get("endLine", line)
    column = location.get("column", 0)
    end_column = location.get("endColumn", 0)
    
    if line == end_line:
        return f"{file_path}:{line}"
    else:
        return f"{file_path}:{line}-{end_line}"


def format_severity(severity: str) -> str:
    """Format severity with emoji"""
    severity_map = {
        "critical": "🔴 Critical",
        "high": "🟠 High",
        "medium": "🟡 Medium",
        "low": "🔵 Low"
    }
    return severity_map.get(severity.lower(), severity.capitalize())


def format_confidence(confidence: str) -> str:
    """Format confidence level"""
    return confidence.capitalize() if confidence else "Unknown"


def generate_markdown_summary(
    sast_findings: List[Dict[str, Any]],
    sca_findings: List[Dict[str, Any]],
    repo_name: str,
    branch_name: str,
    deployment_slug: str
) -> str:
    """Generate markdown summary for pipeline logs"""
    
    lines = []
    lines.append("# Semgrep Security Scan Summary\n")
    lines.append(f"**Repository:** {repo_name}")
    lines.append(f"**Branch:** {branch_name}")
    lines.append(f"**Scan Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Summary statistics
    total_sast = len(sast_findings)
    total_sca = len(sca_findings)
    total = total_sast + total_sca
    
    lines.append("## Summary Statistics\n")
    lines.append(f"- **Total Findings:** {total}")
    lines.append(f"- **SAST Findings:** {total_sast}")
    lines.append(f"- **SCA Findings:** {total_sca}\n")
    
    # Severity breakdown
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in sast_findings + sca_findings:
        sev = finding.get("severity", "low").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1
    
    lines.append("## Severity Breakdown\n")
    for sev in ["critical", "high", "medium", "low"]:
        count = severity_counts[sev]
        if count > 0:
            lines.append(f"- {format_severity(sev)}: {count}")
    lines.append("")
    
    # SAST Findings
    if sast_findings:
        lines.append("## SAST Findings (Source Code Analysis)\n")
        
        for idx, finding in enumerate(sast_findings[:50], 1):  # Limit to 50 for readability
            lines.append(f"### Finding {idx}: {finding.get('rule', {}).get('name', 'Unknown Rule')}\n")
            
            # Basic info
            severity = finding.get("severity", "unknown")
            confidence = finding.get("confidence", "unknown")
            status = finding.get("status", "open")
            
            lines.append(f"- **Severity:** {format_severity(severity)}")
            lines.append(f"- **Confidence:** {format_confidence(confidence)}")
            lines.append(f"- **Status:** {status.capitalize()}")
            
            # Location
            location = finding.get("location")
            if location:
                loc_str = format_code_location(location)
                line_of_code_url = finding.get("line_of_code_url", "")
                if line_of_code_url:
                    lines.append(f"- **Location:** [{loc_str}]({line_of_code_url})")
                else:
                    lines.append(f"- **Location:** {loc_str}")
            
            # Rule message
            rule = finding.get("rule", {})
            message = rule.get("message") or finding.get("rule_message", "No description available")
            lines.append(f"- **Description:** {message}")
            
            # Assistant data (if available)
            assistant = finding.get("assistant", {})
            if assistant:
                rule_explanation = assistant.get("rule_explanation", {})
                if rule_explanation:
                    explanation = rule_explanation.get("explanation")
                    if explanation:
                        lines.append(f"\n**Explanation:**\n{explanation}\n")
                
                guidance = assistant.get("guidance", {})
                if guidance:
                    summary = guidance.get("summary")
                    instructions = guidance.get("instructions")
                    if summary:
                        lines.append(f"**Fix Guidance:** {summary}")
                    if instructions:
                        lines.append(f"\n**Fix Instructions:**\n{instructions}\n")
                
                autofix = assistant.get("autofix", {})
                if autofix:
                    fix_code = autofix.get("fix_code")
                    if fix_code:
                        lines.append("**Auto-Fix Code:**")
                        lines.append("```")
                        lines.append(fix_code)
                        lines.append("```\n")
            
            # Rule metadata
            if rule:
                cwe_names = rule.get("cweNames", [])
                owasp_names = rule.get("owaspNames", [])
                if cwe_names:
                    lines.append(f"- **CWE:** {', '.join(cwe_names)}")
                if owasp_names:
                    lines.append(f"- **OWASP:** {', '.join(owasp_names)}")
            
            # Finding URL
            finding_id = finding.get("id")
            if finding_id:
                finding_url = f"https://semgrep.dev/orgs/{deployment_slug}/findings/{finding_id}"
                lines.append(f"- **View in Semgrep:** [Link]({finding_url})")
            
            lines.append("")
        
        if len(sast_findings) > 50:
            lines.append(f"\n*... and {len(sast_findings) - 50} more SAST findings. View all in Semgrep dashboard.*\n")
    
    # SCA Findings
    if sca_findings:
        lines.append("## SCA Findings (Supply Chain Analysis)\n")
        
        for idx, finding in enumerate(sca_findings[:50], 1):  # Limit to 50
            lines.append(f"### Finding {idx}: {finding.get('rule', {}).get('name', 'Unknown Rule')}\n")
            
            # Basic info
            severity = finding.get("severity", "unknown")
            confidence = finding.get("confidence", "unknown")
            status = finding.get("status", "open")
            reachability = finding.get("reachability", "unknown")
            
            lines.append(f"- **Severity:** {format_severity(severity)}")
            lines.append(f"- **Confidence:** {format_confidence(confidence)}")
            lines.append(f"- **Status:** {status.capitalize()}")
            lines.append(f"- **Reachability:** {reachability.replace('_', ' ').title()}")
            
            # Dependency info
            found_dependency = finding.get("found_dependency", {})
            if found_dependency:
                package = found_dependency.get("package", "Unknown")
                version = found_dependency.get("version", "Unknown")
                transitivity = found_dependency.get("transitivity", "unknown")
                lines.append(f"- **Package:** {package}@{version}")
                lines.append(f"- **Transitivity:** {transitivity.capitalize()}")
            
            # Vulnerability identifier
            vuln_id = finding.get("vulnerability_identifier", "")
            if vuln_id:
                lines.append(f"- **Vulnerability:** {vuln_id}")
            
            # Fix recommendations
            fix_recommendations = finding.get("fix_recommendations", [])
            if fix_recommendations:
                lines.append("\n**Fix Recommendations:**")
                for rec in fix_recommendations:
                    pkg = rec.get("package", "Unknown")
                    ver = rec.get("version", "Unknown")
                    lines.append(f"- Update to {pkg}@{ver}")
            
            # Rule message
            rule = finding.get("rule", {})
            message = rule.get("message") or finding.get("rule_message", "No description available")
            lines.append(f"- **Description:** {message}")
            
            # Location
            location = finding.get("location")
            if location:
                loc_str = format_code_location(location)
                line_of_code_url = finding.get("line_of_code_url", "")
                if line_of_code_url:
                    lines.append(f"- **Location:** [{loc_str}]({line_of_code_url})")
                else:
                    lines.append(f"- **Location:** {loc_str}")
            
            # Finding URL
            finding_id = finding.get("id")
            if finding_id:
                finding_url = f"https://semgrep.dev/orgs/{deployment_slug}/findings/{finding_id}"
                lines.append(f"- **View in Semgrep:** [Link]({finding_url})")
            
            lines.append("")
        
        if len(sca_findings) > 50:
            lines.append(f"\n*... and {len(sca_findings) - 50} more SCA findings. View all in Semgrep dashboard.*\n")
    
    # Footer
    lines.append("---\n")
    lines.append(f"**View all findings in Semgrep:** https://semgrep.dev/orgs/{deployment_slug}/findings?repo={repo_name}&ref={branch_name}")
    
    return "\n".join(lines)


def generate_test_results_format(
    sast_findings: List[Dict[str, Any]],
    sca_findings: List[Dict[str, Any]],
    repo_name: str,
    branch_name: str
) -> Dict[str, Any]:
    """
    Generate test results format for Azure DevOps tab view
    This creates a structure that can be published as test results
    """
    
    test_results = {
        "testResults": [],
        "summary": {
            "total": len(sast_findings) + len(sca_findings),
            "sast": len(sast_findings),
            "sca": len(sca_findings),
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }
    }
    
    # Process SAST findings
    for finding in sast_findings:
        severity = finding.get("severity", "low").lower()
        if severity in test_results["summary"]:
            test_results["summary"][severity] += 1
        
        location = finding.get("location", {})
        rule = finding.get("rule", {})
        
        test_result = {
            "testCaseTitle": rule.get("name", "Unknown Rule"),
            "outcome": "Failed",  # All findings are "failures" in test results context
            "errorMessage": rule.get("message") or finding.get("rule_message", "Security finding detected"),
            "stackTrace": format_code_location(location),
            "severity": severity,
            "confidence": finding.get("confidence", "unknown"),
            "findingType": "SAST",
            "findingId": str(finding.get("id", "")),
            "filePath": location.get("filePath", ""),
            "line": location.get("line", 0),
            "details": {}
        }
        
        # Add assistant data to details
        assistant = finding.get("assistant", {})
        if assistant:
            test_result["details"]["assistant"] = assistant
        
        # Add rule metadata
        if rule:
            test_result["details"]["cwe"] = rule.get("cweNames", [])
            test_result["details"]["owasp"] = rule.get("owaspNames", [])
        
        test_results["testResults"].append(test_result)
    
    # Process SCA findings
    for finding in sca_findings:
        severity = finding.get("severity", "low").lower()
        if severity in test_results["summary"]:
            test_results["summary"][severity] += 1
        
        location = finding.get("location", {})
        rule = finding.get("rule", {})
        found_dependency = finding.get("found_dependency", {})
        
        test_result = {
            "testCaseTitle": f"{rule.get('name', 'Unknown Rule')} - {found_dependency.get('package', 'Unknown')}",
            "outcome": "Failed",
            "errorMessage": rule.get("message") or finding.get("rule_message", "Vulnerable dependency detected"),
            "stackTrace": format_code_location(location),
            "severity": severity,
            "confidence": finding.get("confidence", "unknown"),
            "findingType": "SCA",
            "findingId": str(finding.get("id", "")),
            "filePath": location.get("filePath", ""),
            "line": location.get("line", 0),
            "reachability": finding.get("reachability", "unknown"),
            "vulnerabilityId": finding.get("vulnerability_identifier", ""),
            "package": found_dependency.get("package", ""),
            "version": found_dependency.get("version", ""),
            "details": {
                "fixRecommendations": finding.get("fix_recommendations", [])
            }
        }
        
        test_results["testResults"].append(test_result)
    
    return test_results


def main():
    """Main execution function"""
    start_time = time.time()
    metrics = get_metrics_collector()
    
    try:
        # Check if summary generation is enabled
        if not _env_bool("GENERATE_SUMMARY", True):
            logger.info("Summary generation is disabled. Skipping.")
            sys.exit(0)
        
        # Get configuration
        token = os.getenv("SEMGREP_APP_TOKEN", "")
        if not token:
            logger.error("SEMGREP_APP_TOKEN is not set")
            sys.exit(1)
        
        deployment_id = os.getenv("DEPLOYMENT_ID", "15145")
        repo_name = os.getenv("BUILD_REPOSITORY_NAME", "")
        branch_name = os.getenv("BUILD_SOURCEBRANCHNAME", "")
        summary_display_mode = os.getenv("SUMMARY_DISPLAY_MODE", "Both")
        
        if not repo_name:
            logger.error("BUILD_REPOSITORY_NAME is not set")
            sys.exit(1)
        
        logger.info(f"Generating summary for {repo_name} (branch: {branch_name})")
        
        # Create session
        session = _requests_session()
        
        # Get deployment slug (with caching)
        deployment_slug = get_deployment_slug(session, token)
        
        # Fetch findings (with retry and partial failure handling)
        logger.info("Fetching SAST findings...")
        try:
            sast_findings = get_findings(session, token, deployment_slug, repo_name, branch_name, "sast")
        except Exception as e:
            logger.error(f"Failed to fetch SAST findings: {e}")
            sast_findings = []  # Continue with empty list (partial failure)
        
        logger.info("Fetching SCA findings...")
        try:
            sca_findings = get_findings(session, token, deployment_slug, repo_name, branch_name, "sca")
        except Exception as e:
            logger.error(f"Failed to fetch SCA findings: {e}")
            sca_findings = []  # Continue with empty list (partial failure)
        
        # Generate outputs based on display mode
        if summary_display_mode in ("Logs Only", "Both"):
            markdown = generate_markdown_summary(sast_findings, sca_findings, repo_name, branch_name, deployment_slug)
            
            # Write markdown to file for task to read
            output_file = os.path.join(os.getcwd(), "semgrep_summary.md")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(markdown)
            
            logger.info(f"Markdown summary written to {output_file}")
            
            # Also print to stdout for pipeline logs
            print("\n" + "="*80)
            print("SEMGREP SECURITY SCAN SUMMARY")
            print("="*80 + "\n")
            print(markdown)
            print("\n" + "="*80 + "\n")
        
        if summary_display_mode in ("Tab Only", "Both"):
            test_results = generate_test_results_format(sast_findings, sca_findings, repo_name, branch_name)
            
            # Write test results to file
            output_file = os.path.join(os.getcwd(), "semgrep_test_results.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(test_results, f, indent=2)
            
            logger.info(f"Test results format written to {output_file}")
        
        duration = time.time() - start_time
        
        # Record metrics
        if metrics:
            summary_markdown_path = os.path.join(os.getcwd(), 'semgrep_summary.md')
            test_results_path = os.path.join(os.getcwd(), 'semgrep_test_results.json')
            markdown_generated = os.path.exists(summary_markdown_path)
            test_results_generated = os.path.exists(test_results_path)
            metrics.record_summary(
                len(sast_findings) + len(sca_findings),
                markdown_generated,
                test_results_generated,
                duration
            )
        
        logger.info(f"Summary generation completed successfully in {duration:.2f}s")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
