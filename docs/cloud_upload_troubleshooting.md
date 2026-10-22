# Cloud input files

**Compute → Data Import → Upload Data from Cloud** reads supported analysis inputs
under `datastore/` in the configured S3 bucket. Saved Explore scenarios are separate
root-level `.data` and `.metadata` objects; their presence does not mean the sample
input tree exists.

The browser lists one directory at a time using paginated `ListObjectsV2` with a
prefix and delimiter. Keys use POSIX separators on Windows and Linux. Opening the
panel starts a background listing; **Refresh files** retries it without a page
reload. Empty directories and storage failures have different messages. Double
click a folder to navigate, or a file to import it.

The compact panel shows the current folder name and an icon-only refresh action.
At the bottom, **Load this folder** imports all supported files directly in the
open folder as one batch. Subfolders are excluded and the count on the button
reflects the displayed input files. A folder import is applied only after every
file passes import/schema checks. Multiple files for the same layer reject the
batch with their filenames, so alternative scenarios cannot silently overwrite
one another. Keep one input per layer in a folder, or load alternatives individually.
The folder button is disabled while imports run or when no input files are present.

Each file has a selection checkbox, with **Select all files** above the list. When
files are checked, the bottom action becomes **Load selected (n)** and imports
only those files. With no selection it remains **Load this folder**. Navigation
and refresh clear the selection.

You can also drag a file, or the checked group, onto the existing upload area
above the cloud panel. Dragging an unchecked file selects that file alone. The
browser sends only sample-file paths; S3 downloads still run in the background
import worker. Source objects are copied into the analysis rather than moved.
The drop handler accepts supported sample inputs from one folder under
`datastore/` and applies the same duplicate-layer, failure and cancellation rules
as the folder action. This internal drag format is enabled only on the Compute
impact upload area; other file upload widgets keep their local-file behaviour.

Cloud downloads run in the cancellable import worker, are staged in temporary
files using 1 MiB reads, and use the same schema detection, preprocessing and size
limits as local uploads. Clear or a newer import prevents stale results from being
published. The bundled **Load Sample Scenario** button also works without an S3
connection.

## Empty tree or missing files

Check `datastore/` rather than the entire bucket, using the same credentials and
bucket configuration as the app. The browser needs `s3:ListBucket` and downloads
need `s3:GetObject` for the selected inputs. If a known input was deleted, S3
version history may allow recovery when bucket versioning was enabled. The app
does not automatically restore deleted files.

On 21 October 2026, the missing sample tree was recovered from versions preceding
the bulk deletion on 15 June 2026 at 20:47 UTC: 95 objects (92 supported input files,
plus folder markers and a README) under Dar es Salaam, Nablus, Nairobi and Rapti.
Objects deleted in earlier cleanup operations were left deleted. Saved scenario
keys and ETags were verified unchanged. The recovery receipt is retained locally
under `_gelistirme_dosyalar/cloud_upload_repair/restore_receipt.json`.

`scripts/clear_s3_bucket.py` deletes the entire configured bucket's current objects,
including sample inputs. It is not a scenario-only cleanup command.

Copy updated application files to the server and rebuild the existing service to
apply the browser/import changes:

```bash
docker compose up --build -d tc-app
```

This restarts active application sessions. The S3 data recovery is independent of
deployment and is already visible to existing servers after refreshing their list.

See [upload limits and disconnect troubleshooting](upload_troubleshooting.md) and
the [AWS directory-listing API](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/paginator/ListObjectsV2.html).
