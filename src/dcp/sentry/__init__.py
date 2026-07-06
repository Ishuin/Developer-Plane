"""The Sentry: filesystem intelligence.

Watches the filesystem, discovers projects, and builds the Project Genome.
"""

from dcp.sentry.discovery import ProjectDiscovery
from dcp.sentry.genome import build_genome
from dcp.sentry.scanner import ScanInProgress, ScanManager
from dcp.sentry.watcher import SentryWatcher

__all__ = [
    "ProjectDiscovery",
    "ScanInProgress",
    "ScanManager",
    "SentryWatcher",
    "build_genome",
]
