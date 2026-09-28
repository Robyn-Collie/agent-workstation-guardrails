"""Zero-dependency secret scanner. Standard library only."""

from secret_scan.scanner import Finding, scan_text

__all__ = ["Finding", "scan_text"]
