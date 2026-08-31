# TA-wingpy

TA-wingpy is a Splunk Technology Add-on for onboarding wingpy NDJSON logs.

It is intentionally limited to ingestion and normalization:

- It defines the `wingpy_log` sourcetype.
- It expects one JSON object per log line.
- It extracts fields at search time with `KV_MODE = json`.
- It normalizes a few fields for CIM-oriented searches.
- It can be deployed on standalone Splunk, distributed deployments, forwarders, indexers, and search heads.

## Logging Requirements

Wingpy must write newline-delimited JSON where `timestamp` is the first field in each line and uses ISO 8601 with millisecond precision.

Example:

```json
{"timestamp":"2026-08-24T14:06:47.107+02:00","level":"INFO","message":"Security event","answer":"42","user":"fkj@wingmen.security"}
```

Use the dedicated wingpy helper for this format:

```python
import wingpy
from wingpy.logging import logger

wingpy.log_to_splunk_file("INFO", "wingpy.log")
logger.bind(answer="42", user="fkj@wingmen.security").info("Security event")
```

## Installation

Install the generated `TA-wingpy-<version>.spl` package from the public `wingmendk/TA-wingpy` GitHub releases page, or unpack it into `$SPLUNK_HOME/etc/apps/TA-wingpy`.

Restart Splunk after installation if your deployment model requires it.

## Deployment Notes

- Keep shipped defaults in `default/` unchanged.
- Put environment-specific overrides in `local/`, for example local index selection or monitored file paths.
- The default monitor stanza watches `/var/log/wingpy.log`, sets `sourcetype = wingpy_log`, and writes to the `wingpy` index.
- If your forwarder or indexer uses another path or index, override only those values in `local/inputs.conf`.

## Maintainer Release Flow

- The checked-in source of truth for the app lives in this directory's `app.manifest` and `default/app.conf`.
- `tools/build_ta.py` validates and packages the TA. It does not rewrite metadata during packaging.
- `tools/sync_ta_release.py` is the explicit release-prep step that updates TA versioned metadata before tagging.
- CI publishes TA release assets to the GitHub repository where the workflow runs.

Recommended sequence:

1. Choose the release version and create the release tag in `v<version>` format.
2. Run `python tools/sync_ta_release.py --tag v<version>`.
3. Review and commit the metadata diff in `app.manifest` and `default/app.conf`.
4. Push the release tag.
5. GitHub Actions validates metadata, builds the `.spl`, and publishes it to the current repository's GitHub release.
6. Splunkbase publishing is currently disabled in CI while this repository is private.
7. Re-enable the `splunkbase_publish` job in `.github/workflows/release.yml` when ready to publish to Splunkbase.

Required repository secrets for the Splunkbase job:

- `SPLUNKBASE_UPLOAD_URL`
- `SPLUNKBASE_API_TOKEN`
- `SPLUNKBASE_APP_ID` (optional, but recommended)

## Included Files

- `default/app.conf` contains Splunk app metadata.
- `default/inputs.conf` contains the default file monitor.
- `default/props.conf` configures NDJSON timestamp parsing and field extraction.
- `default/eventtypes.conf` and `default/tags.conf` add a minimal CIM normalization layer.
- `license-eula.txt`, `LICENSE`, `NOTICE`, and `AUTHORS` document licensing and attribution.


