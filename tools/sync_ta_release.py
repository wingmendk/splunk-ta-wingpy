# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2026 Wingmen Solutions ApS
# This file is part of wingpy, distributed under the terms of the GNU GPLv3.
# See the LICENSE, NOTICE, and AUTHORS files for more information.

"""
Synchronize checked-in TA release metadata before a tagged release.
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from build_ta import (
    APP_CONF_PATH,
    APP_MANIFEST_PATH,
    LICENSE_NAME,
    LICENSE_URI,
    RELEASE_NOTES_NAME,
    RELEASE_NOTES_TEXT,
    TA_DESCRIPTION,
    TA_NAME,
    TA_TITLE,
    expected_release_notes_uri,
    load_manifest,
    render_app_conf,
    validate_source_metadata,
    version_from_tag,
)


def sync_manifest(version: str, release_date: str, tag: str) -> None:
    """
    Synchronize the checked-in TA app.manifest file.

    Parameters
    ----------
    version
        TA project version.
    release_date
        Release date to write in ISO format.
    tag
        Git tag to reference in the release notes URI.

    Raises
    ------
    ValueError
        If the manifest cannot be normalized.
    """
    manifest = load_manifest(APP_MANIFEST_PATH)
    info = manifest.setdefault("info", {})
    identity = info.setdefault("id", {})

    info["title"] = TA_TITLE
    identity["name"] = TA_NAME
    identity["version"] = version
    info["releaseDate"] = release_date
    info["description"] = TA_DESCRIPTION
    info["license"] = {
        "name": LICENSE_NAME,
        "text": "license-eula.txt",
        "uri": LICENSE_URI,
    }
    info["releaseNotes"] = {
        "name": RELEASE_NOTES_NAME,
        "text": RELEASE_NOTES_TEXT,
        "uri": expected_release_notes_uri(tag),
    }

    APP_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def sync_app_conf(version: str) -> None:
    """
    Synchronize the checked-in TA app.conf file.

    Parameters
    ----------
    version
        TA project version.

    Raises
    ------
    OSError
        If the file cannot be written.
    """
    APP_CONF_PATH.write_text(render_app_conf(version), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments for TA release metadata synchronization.

    Returns
    -------
    argparse.Namespace
        Parsed CLI arguments.

    Raises
    ------
    SystemExit
        If invalid arguments are supplied.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        required=True,
        help="Git tag to reference in the manifest release notes URI.",
    )
    parser.add_argument(
        "--release-date",
        default=date.today().isoformat(),
        help="Release date in ISO 8601 format. Defaults to today.",
    )
    return parser.parse_args()


def main() -> int:
    """
    Synchronize TA metadata for a release.

    Returns
    -------
    int
        Process exit code.

    Raises
    ------
    ValueError
        If synchronization or validation fails.
    """
    args = parse_args()
    tag = args.tag
    version = version_from_tag(tag)

    sync_manifest(version, args.release_date, tag)
    sync_app_conf(version)
    validate_source_metadata(expected_tag=tag)
    print(f"Synchronized TA metadata for {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
