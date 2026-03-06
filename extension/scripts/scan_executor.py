#!/usr/bin/env python3
"""
Semgrep Scan Executor
Handles full and differential (PR) scans using Semgrep CLI
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def install_semgrep():
    """Install or upgrade Semgrep CLI"""
    try:
        logger.info("Installing/upgrading Semgrep CLI...")
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'semgrep'],
            check=True,
            capture_output=True
        )
        logger.info("Semgrep CLI installed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install Semgrep CLI: {e.stderr.decode()}")
        raise


def get_output_path():
    """Get the output path for findings.json"""
    # Try Azure DevOps agent paths
    agent_work_dir = os.getenv('AGENT_WORKFOLDER', '/home/vsts/work')
    if os.path.exists(agent_work_dir):
        output_dir = os.path.join(agent_work_dir, '1', 'a')
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, 'findings.json')
    
    # Fallback to current directory
    return os.path.join(os.getcwd(), 'findings.json')


def run_full_scan(output_path: str):
    """Run a full Semgrep scan"""
    logger.info("Running Semgrep full scan...")
    try:
        cmd = ['semgrep', 'ci', '--json', '--output', output_path]
        logger.debug(f"Executing command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("Full scan completed successfully")
        logger.debug(f"Scan output: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Full scan failed: {e.stderr}")
        return False


def run_pr_scan(output_path: str, pr_id: str, baseline_ref: str, branch: str):
    """Run a differential Semgrep scan for PR"""
    logger.info(f"Running Semgrep PR scan for PR #{pr_id}")
    logger.info(f"Source branch: {branch}")
    logger.info(f"Baseline: {baseline_ref}")
    
    try:
        # Set environment variables for PR scan
        os.environ['SEMGREP_PR_ID'] = pr_id
        os.environ['SEMGREP_BASELINE_REF'] = baseline_ref
        os.environ['SEMGREP_BRANCH'] = branch
        
        # Fetch baseline branch
        logger.info(f"Fetching baseline branch: {baseline_ref}")
        fetch_cmd = ['git', 'fetch', 'origin', baseline_ref.replace('origin/', '')]
        subprocess.run(fetch_cmd, check=True, capture_output=True)
        
        # Run PR scan
        cmd = ['semgrep', 'ci', '--json', '--output', output_path]
        logger.debug(f"Executing command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env=os.environ.copy()
        )
        
        logger.info("PR scan completed successfully")
        logger.debug(f"Scan output: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"PR scan failed: {e.stderr}")
        return False


def main():
    """Main execution function"""
    try:
        # Install Semgrep CLI
        install_semgrep()
        
        # Get configuration from environment
        scan_type = os.getenv('SCAN_TYPE', 'Full Scan')
        output_path = get_output_path()
        
        logger.info(f"Scan type: {scan_type}")
        logger.info(f"Output path: {output_path}")
        
        if scan_type == 'PR Scan':
            pr_id = os.getenv('SYSTEM_PULLREQUEST_PULLREQUESTID', '')
            baseline_ref = os.getenv('BASELINE_REF', 'origin/master')
            
            # Extract branch name from BUILD_SOURCEBRANCH
            source_branch = os.getenv('BUILD_SOURCEBRANCH', '')
            if source_branch.startswith('refs/heads/'):
                branch = source_branch.replace('refs/heads/', '')
            elif source_branch.startswith('refs/pull/'):
                # For PR builds, use the source branch
                branch = os.getenv('SYSTEM_PULLREQUEST_SOURCEBRANCH', source_branch)
            else:
                branch = source_branch
            
            if not pr_id:
                logger.warning("PR ID not found, falling back to full scan")
                success = run_full_scan(output_path)
            else:
                success = run_pr_scan(output_path, pr_id, baseline_ref, branch)
        else:
            # Full scan
            success = run_full_scan(output_path)
        
        if success:
            # Verify output file exists
            if os.path.exists(output_path):
                logger.info(f"Findings saved to: {output_path}")
                sys.exit(0)
            else:
                logger.error(f"Output file not found: {output_path}")
                sys.exit(1)
        else:
            logger.error("Scan execution failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
