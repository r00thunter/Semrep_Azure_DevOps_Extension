#!/usr/bin/env python3
"""
Metrics and reporting utilities for Semgrep Azure DevOps Extension

Tracks:
- Scan statistics
- Ticket creation metrics
- PR creation metrics
- Performance metrics
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


logger = logging.getLogger("metrics")


@dataclass
class ScanMetrics:
    """Metrics for scan execution"""
    scan_type: str
    findings_count: int
    sast_count: int
    sca_count: int
    scan_duration_seconds: float
    timestamp: str


@dataclass
class TicketMetrics:
    """Metrics for ticket creation"""
    ticket_type: str  # SAST, SCA, License
    created_count: int
    skipped_count: int
    failed_count: int
    duration_seconds: float
    timestamp: str


@dataclass
class PRMetrics:
    """Metrics for PR creation"""
    prs_created: int
    findings_fixed: int
    branches_created: int
    duration_seconds: float
    timestamp: str


@dataclass
class SummaryMetrics:
    """Metrics for summary generation"""
    findings_included: int
    markdown_generated: bool
    test_results_generated: bool
    duration_seconds: float
    timestamp: str


class MetricsCollector:
    """Collects and reports metrics for the extension"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            'scan': None,
            'tickets': [],
            'prs': None,
            'summary': None,
            'start_time': time.time(),
            'total_duration': 0.0
        }
        self.metrics_file = os.path.join(os.getcwd(), 'semgrep_metrics.json')
    
    def record_scan(self, scan_type: str, findings_count: int, sast_count: int, sca_count: int, duration: float):
        """Record scan metrics"""
        self.metrics['scan'] = asdict(ScanMetrics(
            scan_type=scan_type,
            findings_count=findings_count,
            sast_count=sast_count,
            sca_count=sca_count,
            scan_duration_seconds=duration,
            timestamp=datetime.now().isoformat()
        ))
        logger.info(f"Scan metrics: {findings_count} findings ({sast_count} SAST, {sca_count} SCA) in {duration:.2f}s")
    
    def record_ticket_creation(self, ticket_type: str, created: int, skipped: int, failed: int, duration: float):
        """Record ticket creation metrics"""
        ticket_metrics = asdict(TicketMetrics(
            ticket_type=ticket_type,
            created_count=created,
            skipped_count=skipped,
            failed_count=failed,
            duration_seconds=duration,
            timestamp=datetime.now().isoformat()
        ))
        self.metrics['tickets'].append(ticket_metrics)
        logger.info(f"Ticket metrics ({ticket_type}): {created} created, {skipped} skipped, {failed} failed in {duration:.2f}s")
    
    def record_pr_creation(self, prs_created: int, findings_fixed: int, branches_created: int, duration: float):
        """Record PR creation metrics"""
        self.metrics['prs'] = asdict(PRMetrics(
            prs_created=prs_created,
            findings_fixed=findings_fixed,
            branches_created=branches_created,
            duration_seconds=duration,
            timestamp=datetime.now().isoformat()
        ))
        logger.info(f"PR metrics: {prs_created} PRs created, {findings_fixed} findings fixed in {duration:.2f}s")
    
    def record_summary(self, findings_included: int, markdown: bool, test_results: bool, duration: float):
        """Record summary generation metrics"""
        self.metrics['summary'] = asdict(SummaryMetrics(
            findings_included=findings_included,
            markdown_generated=markdown,
            test_results_generated=test_results,
            duration_seconds=duration,
            timestamp=datetime.now().isoformat()
        ))
        logger.info(f"Summary metrics: {findings_included} findings included in {duration:.2f}s")
    
    def finalize(self):
        """Finalize metrics and save to file"""
        self.metrics['total_duration'] = time.time() - self.metrics['start_time']
        self.metrics['end_time'] = datetime.now().isoformat()
        
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
            logger.info(f"Metrics saved to {self.metrics_file}")
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")
    
    def get_summary(self) -> str:
        """Get human-readable metrics summary"""
        lines = []
        lines.append("## Semgrep Extension Metrics\n")
        
        if self.metrics['scan']:
            scan = self.metrics['scan']
            lines.append(f"**Scan:** {scan['findings_count']} findings ({scan['sast_count']} SAST, {scan['sca_count']} SCA) in {scan['scan_duration_seconds']:.2f}s")
        
        if self.metrics['tickets']:
            total_created = sum(t['created_count'] for t in self.metrics['tickets'])
            total_skipped = sum(t['skipped_count'] for t in self.metrics['tickets'])
            total_failed = sum(t['failed_count'] for t in self.metrics['tickets'])
            lines.append(f"**Tickets:** {total_created} created, {total_skipped} skipped, {total_failed} failed")
        
        if self.metrics['prs']:
            prs = self.metrics['prs']
            lines.append(f"**PRs:** {prs['prs_created']} created, {prs['findings_fixed']} findings fixed")
        
        if self.metrics['summary']:
            summary = self.metrics['summary']
            lines.append(f"**Summary:** {summary['findings_included']} findings included")
        
        lines.append(f"**Total Duration:** {self.metrics['total_duration']:.2f}s")
        
        return "\n".join(lines)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
