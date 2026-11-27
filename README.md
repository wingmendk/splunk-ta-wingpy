# Wingmen Add-on for wingpy (TA-wingpy)

TA-wingpy is a Splunk Technology Add-on for onboarding wingpy NDJSON logs.

Visit [wingpy.net](https://wingpy.net) and
[wingpy.automation.wingmen.dk](https://wingpy.automation.wingmen.dk) for wingpy.

It is intentionally limited to ingestion and normalization:

- It defines the `wingpy_log` sourcetype.
- It expects one JSON object per log line.
- It extracts fields at search time with `KV_MODE = json`.
- It maps a few fields to CIM-oriented names; it does not tag events as CIM data.
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

Install the generated `TA-wingpy-<version>.spl` package from the [GitHub releases page](https://github.com/wingmendk/splunk-ta-wingpy/releases), or unpack it into `$SPLUNK_HOME/etc/apps/TA-wingpy`.

Restart Splunk after installation if your deployment model requires it.

## Deployment Notes

- Keep shipped defaults in `default/` unchanged.
- Put environment-specific configuration in `local/`, for example local index selection or monitored file paths.
- The default monitor stanza watches `/var/log/wingpy.log`, sets `sourcetype = wingpy_log`, and writes to the `wingpy` index.
- Create the `wingpy` index on the indexing tier before ingesting data, or override `index` in `local/inputs.conf` with an existing index. The add-on does not create an index.
- The logging example writes `wingpy.log` in the current working directory, not `/var/log/wingpy.log`. Configure a monitor for the actual log file and ensure the Splunk process can read it.
- In a distributed deployment, configure the monitor on the system reading the file, install the add-on on the parsing/indexing tier for event and timestamp parsing, and install it on search heads for search-time fields.
- Splunk Cloud Victoria does not sync `default/inputs.conf` to indexers. Configure file monitoring on a forwarder that can access the log file, and ensure the destination index exists in Splunk Cloud.
- Search `index=wingpy sourcetype=wingpy_log` to verify ingestion, substituting your index if overridden. Your Splunk role must have access to that index.

For example, to monitor a different file and use an existing index, create
`local/inputs.conf` on the system reading the file:

```ini
[monitor:///var/log/wingpy.log]
disabled = true

[monitor:///path/to/wingpy.log]
disabled = false
index = existing_index
sourcetype = wingpy_log
```

Replace the example path and index with your own. The first stanza disables the
shipped monitor; changing a monitor path requires a new stanza.

## Development

See the [developer guide](https://github.com/wingmendk/splunk-ta-wingpy/blob/main/DEVELOPER.md) for the maintainer release flow.

## Included Files

- `default/app.conf` contains Splunk app metadata.
- `default/inputs.conf` contains the default file monitor.
- `default/props.conf` configures NDJSON timestamp parsing and field extraction, and maps a few fields to CIM-oriented names.
- `license-eula.txt`, `LICENSE`, `NOTICE`, and `AUTHORS` document licensing and attribution.


