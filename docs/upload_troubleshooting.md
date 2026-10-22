# Uploads and server disconnects

Use `solara run tomorrowcities.pages --production --workers 1` for analysis sessions.
Development mode can reload the app when source files change. Docker and Procfile
entry points now explicitly use production mode and one worker; rebuild/redeploy
existing containers to apply those changes. This does not change impact formulas.

## Import behaviour

Impact uploads use lazy browser streams, staged one file at a time in 1 MiB reads
to private temporary files. Temporary files are removed on success and failure.
Normal JSON tables go through pandas once, preserving its type inference.
Completed inputs are published after all reads; map previews wait until then.
One failed file is reported by filename and does not reset the other layers.
Clear or a newer upload prevents a cancelled task from publishing stale results.

Closed table/chart/detail panels do not prepare hidden content. JSON/CSV exports
are generated only when requested. The map cache keeps one preview per layer and
closes replaced widget trees after the new layer list has rendered. Raster point
creation skips nonpositive pixels before making geometries, preserving positive
depths, cell centres, row order and the existing nearest-point/distance method.

Successful imports also checkpoint references to the application’s existing
in-process session storage. This helps when that same session reconnects; it is
not disk persistence and cannot recover a terminated process or a new session.

## Import limits

Defaults are 512 MiB per upload and 10,000,000 raster band values in both the source
and reprojected grids. Oversized inputs produce an error before large raster arrays
are expanded. Crop global GIRI maps to the study area and convert centimetres to
metres before import; upload improvements do not change the unit convention.

Operators can set `TC_MAX_UPLOAD_BYTES` and `TC_MAX_RASTER_VALUES` in the server
environment. These are positive integer limits. Increase them only after checking
available RAM, disk and concurrent use; raising a limit does not reduce memory use.
Temporary disk space must be sufficient for the largest accepted file.

## If disconnects continue

Explore opens empty each time it is entered. Choosing a scenario only selects it;
press **Load Scenario** to load it. The loaded-scenario label identifies the data
currently displayed, even if a different item is selected in the dropdown. Clear
also removes metadata, metric caches and filters, and invalidates pending loads.
Leaving the page has the same invalidation effect. A late download cannot restore
a cleared scenario. Failed loads leave the previous complete scenario in place.
Downloads and tally preparation run in the background; metadata is not fetched
again on each render, and heavy preparation is serialized per user.

The message alone does not distinguish memory exhaustion, process restart, proxy
timeout or a network interruption. Keep the console output around the failure.
Import failures now log their filename and traceback. For the Compose service:

```bash
docker compose logs --tail 200 tc-app
docker compose ps -q tc-app
docker stats --no-stream
```

Inspect the returned container ID with `docker inspect` and review its restart
count/state, memory limit and host/container events around the failure. The current
Compose limit is 5 GiB, shared by all sessions, imported data, map previews and
analysis work. A roughly 70 MB JSON file can require much more RAM when parsed.
Do not infer OOM solely from a disconnect message or an empty current OOM flag.

For Nginx Proxy Manager, verify WebSocket Support is enabled. If logs identify idle
proxy timeouts, review `proxy_read_timeout` and `proxy_send_timeout` for the existing
host (for example 3600s for long sessions). No external proxy setting is changed by
this repository update. Production deployment and WebSocket behaviour are described
in [Solara’s deployment guide](https://solara.dev/documentation/getting_started/deploying/self-hosted)
and the [Nginx WebSocket documentation](https://nginx.org/en/docs/http/websocket.html).

The bounded browser-read and on-demand export approach uses the documented
[Solara FileDrop](https://solara.dev/documentation/components/input/file_drop) and
[FileDownload](https://solara.dev/documentation/components/output/file_download)
interfaces. These changes reduce known memory amplification; they do not establish
the cause of a particular production disconnect without its logs.
