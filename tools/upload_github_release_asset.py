# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2026 Wingmen Solutions ApS
# This file is part of wingpy, distributed under the terms of the GNU GPLv3.
# See the LICENSE, NOTICE, and AUTHORS files for more information.

"""
Upload the generated Splunk TA artifact to a GitHub release.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib import error, parse, request


def github_request(
    method: str,
    url: str,
    token: str,
    data: bytes | None = None,
    content_type: str = "application/json",
) -> Any:
    """
    Execute a GitHub API request.

    Parameters
    ----------
    method
        HTTP method to use.
    url
        GitHub API URL.
    token
        Personal access token used for authentication.
    data
        Optional request body.
    content_type
        Content type for the request body.

    Returns
    -------
    Any
        Parsed JSON response, or None for empty responses.

    Raises
    ------
    urllib.error.HTTPError
        If the GitHub API returns an error response.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        headers["Content-Type"] = content_type

    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req) as response:
        payload = response.read()
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))


def get_or_create_release(repository: str, tag: str, token: str) -> dict[str, Any]:
    """
    Fetch an existing release for the tag or create one if it is missing.

    Parameters
    ----------
    repository
        GitHub repository in owner/name format.
    tag
        Release tag name.
    token
        Personal access token used for authentication.

    Returns
    -------
    dict[str, Any]
        The GitHub release payload.

    Raises
    ------
    urllib.error.HTTPError
        If the GitHub API request fails for reasons other than a missing release.
    """
    release_url = f"https://api.github.com/repos/{repository}/releases/tags/{tag}"
    try:
        return github_request("GET", release_url, token)
    except error.HTTPError as exc:
        if exc.code != 404:
            raise

    payload = json.dumps(
        {
            "tag_name": tag,
            "name": tag,
            "draft": False,
            "prerelease": False,
            "generate_release_notes": True,
        }
    ).encode("utf-8")
    create_url = f"https://api.github.com/repos/{repository}/releases"
    return github_request("POST", create_url, token, data=payload)


def delete_existing_asset(
    release: dict[str, Any],
    repository: str,
    token: str,
    asset_name: str,
) -> None:
    """
    Remove an existing release asset with the same name.

    Parameters
    ----------
    release
        GitHub release payload.
    repository
        GitHub repository in owner/name format.
    token
        Personal access token used for authentication.
    asset_name
        Asset filename to replace.

    Raises
    ------
    urllib.error.HTTPError
        If the delete request fails.
    """
    for asset in release.get("assets", []):
        if asset.get("name") != asset_name:
            continue

        delete_url = (
            f"https://api.github.com/repos/{repository}/releases/assets/{asset['id']}"
        )
        github_request("DELETE", delete_url, token)
        return


def upload_asset(repository: str, tag: str, asset_path: Path, token: str) -> None:
    """
    Upload the TA artifact to the release associated with the tag.

    Parameters
    ----------
    repository
        GitHub repository in owner/name format.
    tag
        Release tag name.
    asset_path
        Artifact path to upload.
    token
        Personal access token used for authentication.

    Raises
    ------
    FileNotFoundError
        If the artifact path does not exist.
    urllib.error.HTTPError
        If GitHub rejects the upload.
    """
    if not asset_path.is_file():
        raise FileNotFoundError(f"Artifact does not exist: {asset_path}")

    release = get_or_create_release(repository, tag, token)
    delete_existing_asset(release, repository, token, asset_path.name)

    upload_url = (
        f"https://uploads.github.com/repos/{repository}/releases/"
        f"{release['id']}/assets?name={parse.quote(asset_path.name)}"
    )
    content_type = mimetypes.guess_type(asset_path.name)[0] or "application/gzip"
    asset_bytes = asset_path.read_bytes()
    github_request(
        "POST",
        upload_url,
        token,
        data=asset_bytes,
        content_type=content_type,
    )


def parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments for GitHub release uploads.

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
    parser.add_argument("--repository", required=True, help="owner/name repository")
    parser.add_argument("--tag", required=True, help="Git tag for the release")
    parser.add_argument("--asset", type=Path, required=True, help="Path to the asset")
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing the GitHub token.",
    )
    return parser.parse_args()


def main() -> int:
    """
    Upload a TA artifact to GitHub.

    Returns
    -------
    int
        Process exit code.

    Raises
    ------
    ValueError
        If the expected token environment variable is missing.
    """
    args = parse_args()
    token = os.getenv(args.token_env)
    if not token:
        raise ValueError(
            f"Environment variable {args.token_env} must contain a GitHub token."
        )

    upload_asset(args.repository, args.tag, args.asset, token)
    print(f"Uploaded {args.asset} to {args.repository}@{args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
