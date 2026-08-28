# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2026 Wingmen Solutions ApS
# This file is part of wingpy, distributed under the terms of the GNU GPLv3.
# See the LICENSE, NOTICE, and AUTHORS files for more information.

"""
Upload a built Splunk TA artifact to Splunk App Store / Splunkbase.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
from pathlib import Path
from typing import Any
from urllib import error, request


def build_multipart_payload(
    *,
    boundary: str,
    fields: dict[str, str],
    file_field_name: str,
    file_path: Path,
) -> bytes:
    """Build a multipart/form-data payload for a file upload request."""
    lines: list[bytes] = []

    for key, value in fields.items():
        lines.extend(
            [
                f"--{boundary}".encode(),
                (f'Content-Disposition: form-data; name="{key}"').encode(),
                b"",
                value.encode("utf-8"),
            ]
        )

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    lines.extend(
        [
            f"--{boundary}".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field_name}"; '
                f'filename="{file_path.name}"'
            ).encode(),
            f"Content-Type: {content_type}".encode(),
            b"",
            file_bytes,
        ]
    )

    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    return b"\r\n".join(lines)


def upload_asset(
    *,
    upload_url: str,
    token: str,
    asset_path: Path,
    version: str,
    tag: str,
    app_id: str | None,
    release_notes: str | None,
    file_field_name: str,
) -> dict[str, Any] | None:
    """Upload an artifact to a configured Splunk App Store endpoint."""
    if not asset_path.is_file():
        raise FileNotFoundError(f"Artifact does not exist: {asset_path}")

    boundary = f"------------------------{secrets.token_hex(16)}"
    fields = {
        "version": version,
        "tag": tag,
    }
    if app_id:
        fields["app_id"] = app_id
    if release_notes:
        fields["release_notes"] = release_notes

    payload = build_multipart_payload(
        boundary=boundary,
        fields=fields,
        file_field_name=file_field_name,
        file_path=asset_path,
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }

    req = request.Request(upload_url, data=payload, headers=headers, method="POST")
    with request.urlopen(req) as response:
        body = response.read()
        if not body:
            return None

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return json.loads(body.decode("utf-8"))

    return None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for Splunk App Store uploads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", type=Path, required=True, help="Path to .spl file")
    parser.add_argument("--tag", required=True, help="Release tag, for example v1.7.0")
    parser.add_argument(
        "--version",
        required=True,
        help="Release version, for example 1.7.0",
    )
    parser.add_argument(
        "--upload-url",
        default=os.getenv("SPLUNKBASE_UPLOAD_URL", ""),
        help=(
            "Full Splunk App Store upload endpoint. Defaults to "
            "SPLUNKBASE_UPLOAD_URL env var."
        ),
    )
    parser.add_argument(
        "--token-env",
        default="SPLUNKBASE_API_TOKEN",
        help="Environment variable containing the Splunk App Store bearer token.",
    )
    parser.add_argument(
        "--app-id",
        default=os.getenv("SPLUNKBASE_APP_ID"),
        help="Optional Splunkbase app identifier.",
    )
    parser.add_argument(
        "--release-notes",
        default=None,
        help="Optional short release notes included with the upload request.",
    )
    parser.add_argument(
        "--file-field-name",
        default="file",
        help="Multipart file field name expected by the upload endpoint.",
    )
    return parser.parse_args()


def main() -> int:
    """Upload a TA build artifact to Splunk App Store."""
    args = parse_args()

    if not args.upload_url:
        raise ValueError(
            "Splunk upload URL is required. Pass --upload-url or set "
            "SPLUNKBASE_UPLOAD_URL."
        )

    token = os.getenv(args.token_env)
    if not token:
        raise ValueError(
            f"Environment variable {args.token_env} must contain a Splunk API token."
        )

    response_payload = upload_asset(
        upload_url=args.upload_url,
        token=token,
        asset_path=args.asset,
        version=args.version,
        tag=args.tag,
        app_id=args.app_id,
        release_notes=args.release_notes,
        file_field_name=args.file_field_name,
    )

    if response_payload is not None:
        print(json.dumps(response_payload, indent=2, ensure_ascii=True))
    print(f"Uploaded {args.asset} for {args.tag} ({args.version})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Splunk upload failed with HTTP {exc.code}: {body}")
        raise
