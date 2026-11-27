# Developer Guide

## Maintainer Release Flow

- The checked-in source of truth for the app lives in this directory's `app.manifest` and `default/app.conf`.
- `tools/build_ta.py` validates and packages the TA. It does not rewrite metadata during packaging.
- `tools/sync_ta_release.py` is the explicit release-prep step that updates TA versioned metadata before tagging.
- CI publishes TA release assets to the GitHub repository where the workflow runs.

Recommended sequence:

1. Choose a new release version and corresponding tag in `v<version>` format.
2. Run `python tools/sync_ta_release.py --tag v<version>`.
3. Review and commit the metadata diff in `app.manifest` and `default/app.conf`.
4. Create the tag on that commit and push the commit and tag.
5. GitHub Actions validates metadata, builds the `.spl`, and publishes it to the current repository's GitHub release.
6. Validate the generated package with Splunk Packaging Toolkit (`slim validate <package.spl>`) and Splunk AppInspect. Resolve their findings before submitting the package to Splunkbase.
7. Submit the package to Splunkbase manually. Automated publishing is disabled and its upload endpoint and authentication must be verified before it is enabled.

Required repository secrets for the Splunkbase job:

- `SPLUNKBASE_UPLOAD_URL`
- `SPLUNKBASE_API_TOKEN`
- `SPLUNKBASE_APP_ID` (optional, but recommended)
