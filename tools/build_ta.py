# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2026 Wingmen Solutions ApS
# This file is part of wingpy, distributed under the terms of the GNU GPLv3.
# See the LICENSE, NOTICE, and AUTHORS files for more information.

"""
Build and verify the Splunk TA artifact for wingpy.
"""

from __future__ import annotations

import argparse
import configparser
import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
TA_SOURCE_DIR: Final[Path] = REPO_ROOT
DEFAULT_OUTPUT_DIR: Final[Path] = REPO_ROOT / "dist"
APP_MANIFEST_PATH: Final[Path] = TA_SOURCE_DIR / "app.manifest"
APP_CONF_PATH: Final[Path] = TA_SOURCE_DIR / "default" / "app.conf"
LICENSE_FILES: Final[tuple[str, ...]] = ("LICENSE", "NOTICE", "AUTHORS")
REQUIRED_TA_FILES: Final[tuple[str, ...]] = (
    "README.md",
    "app.manifest",
    "default/app.conf",
    "default/inputs.conf",
    "default/props.conf",
    "license-eula.txt",
)
TA_DESCRIPTION: Final[str] = (
    "Technology Add-on for onboarding wingpy NDJSON logs into Splunk."
)
TA_NAME: Final[str] = "TA-wingpy"
TA_TITLE: Final[str] = "Wingmen Add-on for wingpy"
TA_AUTHOR: Final[str] = "Wingmen Solutions ApS"
TARGET_WORKLOADS: Final[frozenset[str]] = frozenset(
    {"*", "_search_heads", "_indexers", "_forwarders"}
)
RELEASE_REPOSITORY: Final[str] = "wingmendk/splunk-ta-wingpy"
RELEASE_NOTES_NAME: Final[str] = "README"
RELEASE_NOTES_TEXT: Final[str] = "README.md"
LICENSE_NAME: Final[str] = "GNU General Public License v3 or later"
LICENSE_URI: Final[str] = "https://www.gnu.org/licenses/gpl-3.0.html"
TAG_VERSION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^v(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$"
)


def version_from_tag(tag: str) -> str:
    """
    Parse a release version from a git tag.

    Parameters
    ----------
    tag
        Release tag in v<version> form.

    Returns
    -------
    str
        Parsed semantic version string.

    Raises
    ------
    ValueError
        If the tag does not follow v<version> format.
    """
    version_match = TAG_VERSION_PATTERN.match(tag)
    if version_match is None:
        raise ValueError(
            "Release tags must follow v<semantic-version>, for example v1.7.0. "
            f"Got {tag!r}."
        )

    return version_match.group("version")


def read_manifest_version(manifest_path: Path) -> str:
    """
    Read the TA version from app.manifest.

    Parameters
    ----------
    manifest_path
        Path to app.manifest.

    Returns
    -------
    str
        The configured TA version.

    Raises
    ------
    ValueError
        If the manifest does not define a valid info.id.version value.
    """
    manifest = load_manifest(manifest_path)
    info = manifest.get("info")
    if not isinstance(info, dict):
        raise TypeError("TA app.manifest must contain an info object.")

    identity = info.get("id")
    if not isinstance(identity, dict):
        raise TypeError("TA app.manifest info.id must be an object.")

    version = identity.get("version")
    if not isinstance(version, str) or not version:
        raise TypeError("TA app.manifest info.id.version must be a non-empty string.")

    return version


def render_app_conf(version: str) -> str:
    """
    Render the canonical Splunk app.conf file.

    Parameters
    ----------
    version
        The wingpy package version.

    Returns
    -------
    str
        The canonical app.conf contents.

    Raises
    ------
    ValueError
        If the version is empty.
    """
    if not version:
        raise ValueError("A non-empty version is required to render app.conf.")

    return "\n".join(
        [
            "[launcher]",
            f"author = {TA_AUTHOR}",
            f"description = {TA_DESCRIPTION}",
            f"version = {version}",
            "",
            "[id]",
            f"name = {TA_NAME}",
            f"version = {version}",
            "",
            "[package]",
            f"id = {TA_NAME}",
            "check_for_updates = true",
            "",
            "[install]",
            "state = enabled",
            "",
            "[ui]",
            "is_visible = false",
            f"label = {TA_TITLE}",
            "",
        ]
    )


def expected_release_notes_uri(tag: str) -> str:
    """
    Build the canonical GitHub release-notes URI.

    Parameters
    ----------
    tag
        Release tag name.

    Returns
    -------
    str
        Canonical GitHub release URI for the tag.

    Raises
    ------
    ValueError
        If the tag is empty.
    """
    if not tag:
        raise ValueError("A non-empty tag is required for release notes.")

    return f"https://github.com/{RELEASE_REPOSITORY}/releases/tag/{tag}"


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """
    Read and decode a TA app.manifest file.

    Parameters
    ----------
    manifest_path
        Path to the manifest file.

    Returns
    -------
    dict[str, Any]
        Parsed manifest payload.

    Raises
    ------
    FileNotFoundError
        If the manifest file is missing.
    ValueError
        If the manifest content is invalid JSON.
    """
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_ta_directory(ta_dir: Path) -> None:
    """
    Validate that the TA directory contains the expected files.

    Parameters
    ----------
    ta_dir
        The TA root directory to validate.

    Raises
    ------
    FileNotFoundError
        If one or more required files are missing.
    """
    missing_files = [
        required_file
        for required_file in REQUIRED_TA_FILES
        if not (ta_dir / required_file).is_file()
    ]
    if missing_files:
        missing = ", ".join(sorted(missing_files))
        raise FileNotFoundError(
            f"The TA directory is missing required files: {missing}"
        )


def validate_license_files(root_dir: Path) -> None:
    """
    Validate that legal files required for the package are present.

    Parameters
    ----------
    root_dir
        Repository root directory.

    Raises
    ------
    FileNotFoundError
        If one or more legal files are missing.
    """
    missing_files = [
        file_name for file_name in LICENSE_FILES if not (root_dir / file_name).is_file()
    ]
    if missing_files:
        missing = ", ".join(sorted(missing_files))
        raise FileNotFoundError(f"Missing required legal files: {missing}")


def validate_source_metadata(expected_tag: str | None = None) -> None:
    """
    Validate the checked-in TA metadata against project expectations.

    Parameters
    ----------
    expected_tag
        Optional release tag that the manifest should reference.

    Raises
    ------
    FileNotFoundError
        If required TA files are missing.
    ValueError
        If metadata files do not match the expected release configuration.
    """
    validate_ta_directory(TA_SOURCE_DIR)
    validate_license_files(REPO_ROOT)

    manifest = load_manifest(APP_MANIFEST_PATH)
    version = read_manifest_version(APP_MANIFEST_PATH)
    target_workloads = manifest.get("targetWorkloads")
    if (
        not isinstance(target_workloads, list)
        or not target_workloads
        or any(
            not isinstance(workload, str) or workload not in TARGET_WORKLOADS
            for workload in target_workloads
        )
    ):
        raise ValueError("TA manifest targetWorkloads must contain valid Splunk targets.")

    info = manifest.get("info")
    if not isinstance(info, dict):
        raise TypeError("TA app.manifest must contain an info object.")

    identity = info.get("id")
    if not isinstance(identity, dict):
        raise TypeError("TA app.manifest info.id must be an object.")

    if info.get("title") != TA_TITLE:
        raise ValueError(f"TA title must be {TA_TITLE!r}.")

    if identity.get("name") != TA_NAME:
        raise ValueError(f"TA manifest name must be {TA_NAME!r}.")

    if identity.get("version") != version:
        raise ValueError(
            f"TA manifest version {identity.get('version')!r} does not match {version!r}."
        )

    if info.get("description") != TA_DESCRIPTION:
        raise ValueError("TA manifest description does not match the expected value.")

    license_info = info.get("license")
    if not isinstance(license_info, dict):
        raise TypeError("TA app.manifest license must be an object.")

    if license_info.get("name") != LICENSE_NAME:
        raise ValueError("TA manifest license name does not match the expected value.")

    if license_info.get("text") != "license-eula.txt":
        raise ValueError("TA manifest license text must reference license-eula.txt.")

    if license_info.get("uri") != LICENSE_URI:
        raise ValueError("TA manifest license URI does not match the expected value.")

    release_notes = info.get("releaseNotes")
    if not isinstance(release_notes, dict):
        raise TypeError("TA app.manifest releaseNotes must be an object.")

    if release_notes.get("name") != RELEASE_NOTES_NAME:
        raise ValueError(
            "TA manifest releaseNotes.name does not match the expected value."
        )

    if release_notes.get("text") != RELEASE_NOTES_TEXT:
        raise ValueError(
            "TA manifest releaseNotes.text does not match the expected value."
        )

    release_uri = release_notes.get("uri")
    if not isinstance(release_uri, str):
        raise TypeError("TA manifest releaseNotes.uri must be a string.")

    if expected_tag is not None:
        expected_uri = expected_release_notes_uri(expected_tag)
        if release_uri != expected_uri:
            raise ValueError(
                "TA manifest releaseNotes.uri does not match the expected release tag. "
                f"Expected {expected_uri!r}, got {release_uri!r}."
            )

        expected_version = version_from_tag(expected_tag)
        if version != expected_version:
            raise ValueError(
                "TA manifest version does not match the release tag. "
                f"Expected {expected_version!r}, got {version!r}."
            )
    elif not release_uri.startswith(
        f"https://github.com/{RELEASE_REPOSITORY}/releases"
    ):
        raise ValueError(
            "TA manifest releaseNotes.uri must point to the wingpy releases page or a tagged release."
        )

    source_app_conf = APP_CONF_PATH.read_text(encoding="utf-8")
    expected_app_conf = render_app_conf(version)
    if source_app_conf != expected_app_conf:
        raise ValueError(
            "TA default/app.conf does not match the expected canonical content. "
            "Run the TA release sync helper to normalize it."
        )

    config = configparser.ConfigParser()
    config.read_string(source_app_conf)
    if config["id"]["name"] != TA_NAME or config["package"]["id"] != TA_NAME:
        raise ValueError("TA app.conf identifiers must match the TA name.")

    if config["launcher"]["version"] != version:
        raise ValueError("TA app.conf version does not match the package version.")

    if config["id"]["version"] != version:
        raise ValueError("TA app.conf id version does not match the package version.")

    if config["launcher"]["description"] != TA_DESCRIPTION:
        raise ValueError("TA app.conf description does not match the expected value.")

    if config["ui"]["label"] != TA_TITLE:
        raise ValueError("TA app.conf UI label must match the TA title.")

    if config["launcher"]["author"] != TA_AUTHOR:
        raise ValueError("TA app.conf author does not match the expected value.")

    if config["package"]["check_for_updates"].lower() != "true":
        raise ValueError("TA app.conf package.check_for_updates must be true.")

    if config["install"]["state"] != "enabled":
        raise ValueError("TA app.conf install.state must be enabled.")

    if config["ui"]["is_visible"].lower() != "false":
        raise ValueError("TA app.conf ui.is_visible must be false.")


def prepare_staging_directory() -> Path:
    """
    Create a staging directory for TA packaging.

    Returns
    -------
    Path
        Temporary directory containing the staged TA-wingpy folder.

    Raises
    ------
    FileNotFoundError
        If required source files are missing.
    ValueError
        If the source metadata is invalid.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="wingpy-ta-"))
    staged_ta_dir = temp_dir / TA_NAME
    staged_ta_dir.mkdir(parents=True, exist_ok=True)

    for relative_file in REQUIRED_TA_FILES:
        source_path = REPO_ROOT / relative_file
        destination_path = staged_ta_dir / relative_file
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)

    for license_file in LICENSE_FILES:
        shutil.copy2(REPO_ROOT / license_file, staged_ta_dir / license_file)

    validate_ta_directory(staged_ta_dir)
    return temp_dir


def verify_archive(archive_path: Path, version: str) -> None:
    """
    Verify the built TA archive structure and version metadata.

    Parameters
    ----------
    archive_path
        Path to the generated .spl archive.
    version
        The expected wingpy package version.

    Raises
    ------
    FileNotFoundError
        If the archive or required members are missing.
    ValueError
        If metadata inside the archive does not match expectations.
    """
    if not archive_path.is_file():
        raise FileNotFoundError(f"TA artifact does not exist: {archive_path}")

    expected_manifest = load_manifest(APP_MANIFEST_PATH)
    expected_app_conf = APP_CONF_PATH.read_text(encoding="utf-8")

    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = {member.name for member in archive.getmembers() if member.isfile()}
        required_members = {
            f"{TA_NAME}/{required_file}" for required_file in REQUIRED_TA_FILES
        }
        required_members.update(
            {f"{TA_NAME}/{license_file}" for license_file in LICENSE_FILES}
        )
        missing_members = sorted(required_members - members)
        if missing_members:
            missing = ", ".join(missing_members)
            raise FileNotFoundError(
                f"TA archive is missing required members: {missing}"
            )

        manifest_member = archive.extractfile(f"{TA_NAME}/app.manifest")
        if manifest_member is None:
            raise FileNotFoundError("TA archive does not contain app.manifest.")

        app_conf_member = archive.extractfile(f"{TA_NAME}/default/app.conf")
        if app_conf_member is None:
            raise FileNotFoundError("TA archive does not contain default/app.conf.")

        manifest = json.load(manifest_member)
        if manifest != expected_manifest:
            raise ValueError("TA archive app.manifest does not match the source file.")

        manifest_version = manifest["info"]["id"]["version"]
        if manifest_version != version:
            raise ValueError(
                f"Manifest version {manifest_version} does not match {version}."
            )

        app_conf_text = app_conf_member.read().decode("utf-8")
        if app_conf_text != expected_app_conf:
            raise ValueError(
                "TA archive default/app.conf does not match the source file."
            )

        config = configparser.ConfigParser()
        config.read_string(app_conf_text)
        app_conf_version = config["launcher"]["version"]
        if app_conf_version != version:
            raise ValueError(
                f"app.conf version {app_conf_version} does not match {version}."
            )


def build_ta(output_dir: Path, expected_tag: str | None = None) -> Path:
    """
    Build the Splunk TA archive.

    Parameters
    ----------
    output_dir
        Directory that should receive the generated .spl file.

    Returns
    -------
    Path
        The generated .spl archive path.

    Raises
    ------
    FileNotFoundError
        If required source files are missing.
    ValueError
        If project metadata is invalid.
    """
    validate_source_metadata(expected_tag=expected_tag)
    version = read_manifest_version(APP_MANIFEST_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{TA_NAME}-{version}.spl"

    staging_root = prepare_staging_directory()
    try:
        staged_ta_dir = staging_root / TA_NAME
        if artifact_path.exists():
            artifact_path.unlink()

        with tarfile.open(artifact_path, mode="w:gz") as archive:
            archive.add(staged_ta_dir, arcname=TA_NAME)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    verify_archive(artifact_path, version)
    return artifact_path


def parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments for TA build operations.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.

    Raises
    ------
    SystemExit
        If invalid arguments are provided.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory receiving the generated .spl artifact.",
    )
    parser.add_argument(
        "--verify-archive",
        type=Path,
        help="Verify an existing .spl archive instead of building a new one.",
    )
    parser.add_argument(
        "--verify-built",
        action="store_true",
        help="Verify the version-matched archive in the selected output directory.",
    )
    parser.add_argument(
        "--validate-source",
        action="store_true",
        help="Validate checked-in TA metadata without building an archive.",
    )
    parser.add_argument(
        "--expected-tag",
        help="Require the manifest releaseNotes URI to reference this release tag.",
    )
    return parser.parse_args()


def main() -> int:
    """
    Build or verify the TA archive from the command line.

    Returns
    -------
    int
        Process exit code.

    Raises
    ------
    FileNotFoundError
        If required inputs are missing.
    ValueError
        If metadata validation fails.
    """
    args = parse_args()
    version = read_manifest_version(APP_MANIFEST_PATH)

    if args.validate_source:
        validate_source_metadata(expected_tag=args.expected_tag)
        print("Validated TA source metadata")
        return 0

    if args.verify_archive is not None:
        validate_source_metadata(expected_tag=args.expected_tag)
        verify_archive(args.verify_archive, version)
        print(f"Verified {args.verify_archive}")
        return 0

    if args.verify_built:
        validate_source_metadata(expected_tag=args.expected_tag)
        artifact_path = args.output_dir / f"{TA_NAME}-{version}.spl"
        verify_archive(artifact_path, version)
        print(f"Verified {artifact_path}")
        return 0

    artifact_path = build_ta(args.output_dir, expected_tag=args.expected_tag)
    print(artifact_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
