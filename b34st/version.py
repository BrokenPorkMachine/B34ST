#!/usr/bin/env python3
"""B34ST (B34KER/STAR) - Version Management

Defines version information for B34ST and provides version-related utilities.
"""

from __future__ import annotations

import re

__version__ = "0.6.1b"
__release_name__ = "B34ST_0.6.1b_Beta"
_VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:(?P<stage>a|b|rc)(?P<stage_number>[0-9]+)?)?(?:_beta)?$"
)
_STAGE_ORDER = {"a": 0, "b": 1, "rc": 2, None: 3}


class VersionError(Exception):
    """Exception raised for version-related errors."""

    pass


class B34STVersion:
    """Version information and metadata for B34ST."""

    VERSION = __version__
    RELEASE_NAME = __release_name__
    PROJECT = "FBR34KER"
    STATUS = "Beta"

    @staticmethod
    def get_version_string() -> str:
        """Get the full version string including release name."""
        return f"{B34STVersion.VERSION} ({B34STVersion.RELEASE_NAME})"

    @staticmethod
    def get_project_info() -> dict:
        """Get complete project information."""
        return {
            "project": B34STVersion.PROJECT,
            "version": B34STVersion.VERSION,
            "release_name": B34STVersion.RELEASE_NAME,
            "status": B34STVersion.STATUS,
        }

    @staticmethod
    def validate_version(version: str | None = None) -> bool:
        """Validate version format.

        Returns True if version is valid, False otherwise.
        """
        candidate = B34STVersion.VERSION if version is None else version
        return _VERSION_RE.fullmatch(candidate) is not None

    @staticmethod
    def _version_key(version: str) -> tuple[int, int, int, int, int]:
        match = _VERSION_RE.fullmatch(version)
        if match is None:
            raise VersionError(f"invalid release version: {version!r}")
        stage = match.group("stage")
        stage_number = int(match.group("stage_number") or 0)
        return (
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            _STAGE_ORDER[stage],
            stage_number,
        )

    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """Compare two version strings.

        Returns:
          -1 if version1 < version2
           0 if version1 == version2
           1 if version1 > version2
        """
        key1 = B34STVersion._version_key(version1)
        key2 = B34STVersion._version_key(version2)
        return (key1 > key2) - (key1 < key2)


def main():
    """Display version information."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="b34st-version",
        description="Display B34ST version information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
The B34ST (B34KER/STAR) version is part of the FBR34KER {__version__} release.
This is a Beta version with evidence-based
profile maturity enforcement and deterministic validation.
        """,
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full version information including release details",
    )
    parser.add_argument(
        "--project",
        action="store_true",
        help="Show only project information",
    )
    parser.add_argument(
        "--version-only",
        action="store_true",
        help="Show only the version number",
    )

    args = parser.parse_args(sys.argv[1:])

    if args.version_only:
        print(__version__)
        return 0

    info = B34STVersion.get_project_info()

    if args.project:
        print(f"Project: {info['project']}")
        return 0

    print(f"B34ST {info['version']} ({info['release_name']})")
    print(f"Status: {info['status']}")

    if args.full:
        print("\nComplete B34ST Project Information:")
        print(f"  Project: {info['project']}")
        print(f"  Version: {info['version']}")
        print(f"  Release Name: {info['release_name']}")
        print(f"  Status: {info['status']}")
        print(f"  Source: FBR34KER {__version__} Beta")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
