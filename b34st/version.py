#!/usr/bin/env python3
"""B34ST (B34KER/STAR) - Version Management

Defines version information for B34ST and provides version-related utilities.
"""

__version__ = "0.3.0"
__release_name__ = "B34ST_0.3.0_Beta"


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
    def validate_version() -> bool:
        """Validate version format.

        Returns True if version is valid, False otherwise.
        """
        parts = B34STVersion.VERSION.split(".")
        if len(parts) != 3:
            return False

        for part in parts:
            if not part.isdigit():
                return False

        return True

    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """Compare two version strings.

        Returns:
          -1 if version1 < version2
           0 if version1 == version2
           1 if version1 > version2
        """
        v1_parts = list(map(int, version1.split(".")))
        v2_parts = list(map(int, version2.split(".")))

        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0

            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1

        return 0


def main():
    """Display version information."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="b34st-version",
        description="Display B34ST version information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The B34ST (B34KER/STAR) version is part of the FBR34KER 0.3.0 release.
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
        print(f"\nComplete B34ST Project Information:")
        print(f"  Project: {info['project']}")
        print(f"  Version: {info['version']}")
        print(f"  Release Name: {info['release_name']}")
        print(f"  Status: {info['status']}")
        print(f"  Source: FBR34KER 0.3.0 Beta")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
