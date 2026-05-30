#!/usr/bin/env python3
"""
Semgrep Scan Executor
Handles full and differential (PR) scans using Semgrep CLI
"""

import json
import logging
import os
import subprocess
import sys
from typing import Dict, List, Optional

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _is_debug() -> bool:
    return log_level == 'DEBUG'


def install_semgrep():
    """Install or upgrade Semgrep CLI"""
    try:
        logger.info("Installing/upgrading Semgrep CLI...")
        kwargs = {'check': True, 'text': True}
        if _is_debug():
            kwargs['stdout'] = None
            kwargs['stderr'] = None
        else:
            kwargs['capture_output'] = True

        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'semgrep'],
            **kwargs
        )
        logger.info("Semgrep CLI installed successfully")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ''
        logger.error("Failed to install Semgrep CLI: %s", stderr)
        raise


def get_output_path():
    """Get the output path for findings.json"""
    agent_work_dir = os.getenv('AGENT_WORKFOLDER', '/home/vsts/work')
    if os.path.exists(agent_work_dir):
        output_dir = os.path.join(agent_work_dir, '1', 'a')
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, 'findings.json')

    return os.path.join(os.getcwd(), 'findings.json')


def _build_semgrep_cmd(output_path: str) -> List[str]:
    cmd = ['semgrep', 'ci', '--json', '--output', output_path]
    if _is_debug():
        cmd.append('--verbose')
    return cmd


def _log_findings_summary(output_path: str) -> None:
    if not os.path.exists(output_path):
        logger.warning("Findings file not found at %s", output_path)
        return

    try:
        with open(output_path, encoding='utf-8') as f:
            data = json.load(f)

        results = data.get('results') or []
        errors = data.get('errors') or []
        logger.info("Findings file: %s", output_path)
        logger.info("Semgrep reported %d finding(s), %d error(s)", len(results), len(errors))

        for err in errors[:5]:
            msg = err.get('message') or err.get('type') or str(err)
            logger.warning("Semgrep error: %s", msg)

        preview = 15 if _is_debug() else 5
        for i, finding in enumerate(results[:preview], start=1):
            check_id = finding.get('check_id', 'unknown-rule')
            path = finding.get('path', 'unknown-file')
            line = (finding.get('start') or {}).get('line', '?')
            severity = finding.get('extra', {}).get('severity', finding.get('severity', ''))
            message = (finding.get('extra') or {}).get('message', '')
            logger.info(
                "  [%d] %s (%s) %s:%s %s",
                i, check_id, severity, path, line, message[:120] if message else ''
            )

        if len(results) > preview:
            logger.info("  ... and %d more finding(s)", len(results) - preview)
    except Exception as e:
        logger.warning("Could not parse findings summary: %s", e)


def _run_semgrep(cmd: List[str], env: Optional[Dict[str, str]] = None) -> int:
    """
    Run semgrep and stream stdout/stderr live to pipeline logs.
    Returns the process exit code.
    """
    logger.info("Executing command: %s", ' '.join(cmd))
    logger.info("--- semgrep ci output (begin) ---")

    proc = subprocess.run(
        cmd,
        env=env,
        check=False,
    )

    logger.info("--- semgrep ci output (end) ---")
    logger.info("semgrep ci exit code: %s", proc.returncode)
    return proc.returncode


def _interpret_exit_code(exit_code: int, output_path: str) -> bool:
    if exit_code == 0:
        logger.info("Semgrep scan completed with no blocking findings")
        _log_findings_summary(output_path)
        return True

    if exit_code == 1 and os.path.exists(output_path):
        logger.warning(
            "Semgrep exited with code 1 (findings or policy failure). See output above and summary below."
        )
        _log_findings_summary(output_path)
        return False

    logger.error("Semgrep scan failed with exit code %s", exit_code)
    return False


def run_full_scan(output_path: str):
    """Run a full Semgrep scan"""
    logger.info("Running Semgrep full scan...")
    cmd = _build_semgrep_cmd(output_path)
    exit_code = _run_semgrep(cmd)
    return _interpret_exit_code(exit_code, output_path)


def run_pr_scan(output_path: str, pr_id: str, baseline_ref: str, branch: str):
    """Run a differential Semgrep scan for PR"""
    logger.info("Running Semgrep PR scan for PR #%s", pr_id)
    logger.info("Source branch: %s", branch)
    logger.info("Baseline: %s", baseline_ref)

    try:
        os.environ['SEMGREP_PR_ID'] = pr_id
        os.environ['SEMGREP_BASELINE_REF'] = baseline_ref
        os.environ['SEMGREP_BRANCH'] = branch

        logger.info("Fetching baseline branch: %s", baseline_ref)
        fetch_cmd = ['git', 'fetch', 'origin', baseline_ref.replace('origin/', '')]
        fetch_kwargs = {'check': True, 'text': True}
        if _is_debug():
            fetch_kwargs['stdout'] = None
            fetch_kwargs['stderr'] = None
        else:
            fetch_kwargs['capture_output'] = True
        subprocess.run(fetch_cmd, **fetch_kwargs)

        cmd = _build_semgrep_cmd(output_path)
        exit_code = _run_semgrep(cmd, env=os.environ.copy())
        return _interpret_exit_code(exit_code, output_path)

    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ''
        logger.error("PR scan setup failed: %s", stderr)
        return False


def main():
    """Main execution function"""
    try:
        install_semgrep()

        scan_type = os.getenv('SCAN_TYPE', 'Full Scan')
        output_path = get_output_path()

        logger.info("Scan type: %s", scan_type)
        logger.info("Output path: %s", output_path)
        logger.info("Log level: %s", log_level)

        if scan_type == 'PR Scan':
            pr_id = os.getenv('SYSTEM_PULLREQUEST_PULLREQUESTID', '')
            baseline_ref = os.getenv('BASELINE_REF', 'origin/master')

            source_branch = os.getenv('BUILD_SOURCEBRANCH', '')
            if source_branch.startswith('refs/heads/'):
                branch = source_branch.replace('refs/heads/', '')
            elif source_branch.startswith('refs/pull/'):
                branch = os.getenv('SYSTEM_PULLREQUEST_SOURCEBRANCH', source_branch)
            else:
                branch = source_branch

            if not pr_id:
                logger.warning("PR ID not found, falling back to full scan")
                success = run_full_scan(output_path)
            else:
                success = run_pr_scan(output_path, pr_id, baseline_ref, branch)
        else:
            success = run_full_scan(output_path)

        if success:
            if os.path.exists(output_path):
                logger.info("Findings saved to: %s", output_path)
                sys.exit(0)
            logger.error("Output file not found: %s", output_path)
            sys.exit(1)

        logger.error("Scan execution failed")
        sys.exit(1)

    except Exception as e:
        logger.error("Unexpected error: %s", str(e), exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
