# Compute/Explore fail after a Docker rebuild

An error such as:

```text
AttributeError: module 'reacton.ipyvuetify' has no attribute 'ExpansionPanelHeader'
```

indicates an incompatible widget API. Both pages use Vuetify 2 expansion panels;
the custom Vue templates and header CSS also target that generation. Renaming
one panel component is not a complete migration to Vuetify 3.

The reported deployment served `@widgetti/solara-vuetify3-app` assets while the
local working installation used the Vue 2 / Vuetify 2 stack. The theme file was
reachable, so a missing theme asset was not established as the cause of the
header colour change. Solara selects its rendering path from the installed
ipyvuetify version; see the [Solara changelog](https://solara.dev/changelog).

## Rebuild with the tested stack

The repository now pins the UI and server packages in both installation entry points:

| Package | Version |
| --- | --- |
| solara | 1.44.1 |
| solara-ui | 1.44.1 (required by solara) |
| solara-server | 1.44.1 (required by solara) |
| ipyvue | 1.11.2 |
| ipyvuetify | 1.11.1 |
| reacton | 1.9.1 |
| uvicorn | 0.34.0 |
| starlette | 0.46.0 |
| websockets | 15.0 |

An additional startup failure can occur before any page is loaded:

```text
ImportError: cannot import name 'LOOP_CHOICES' from 'uvicorn.main'
```

Solara 1.44.1 imports `LOOP_CHOICES` directly from Uvicorn's CLI module. Newer
Uvicorn versions no longer expose that API. Pinning the UI alone does not
constrain this server dependency. The matching server versions above prevent
the reported import failure; do not edit Uvicorn files inside `site-packages`.
Docker now checks `python -m solara run --help` during the image build so a CLI
import incompatibility fails the build instead of causing a restarting container.

The pinned combination was checked in a new Python 3.10 virtual environment:
`pip check`, the real CLI `run --help`, both page panel components (including
callbacks), and a minimal production-mode Solara server returning HTTP 200 with
Vuetify 2 frontend assets. The Docker daemon was unavailable locally, so this
check does not claim a full Linux container deployment or authenticated app test.
The reproducible helper is `_gelistirme_dosyalar/runtime_smoke/verify_startup.py`.

Copy the updated repository, including `Dockerfile`, `pyproject.toml`, `requirements.txt` and
all new application modules, to the server. From the directory with `compose.yaml`:

```bash
docker compose build --no-cache tc-app
docker compose up -d --force-recreate tc-app
```

The Dockerfile installs the application using `pip install -e .`; changing only
`requirements.txt` does not affect that step. No `down`, volume removal or data
deletion is needed. Recreating the app container restarts active user sessions.

Verify the packages in the running container, rather than on the host:

```bash
docker compose exec tc-app python -c "from importlib.metadata import version; names=['solara','solara-ui','solara-server','ipyvue','ipyvuetify','reacton','uvicorn','starlette','websockets']; print('\n'.join(n+'=='+version(n) for n in names)); from solara.alias import rv; assert hasattr(rv, 'ExpansionPanelHeader') and hasattr(rv, 'ExpansionPanelContent'); from solara.__main__ import main; print('Vuetify 2 panel API and Solara CLI: OK')"
docker compose exec tc-app python -m solara run --help
docker compose logs --tail 100 tc-app
```

Then open the site in a private window or hard-refresh it (Ctrl+Shift+R) and test
Compute and Explore. The expected header colour remains `#1c4220`; no header
colour or calculation formula was changed by this compatibility fix.

If the version output is still different, verify that Compose is building the
directory you updated and that the reverse proxy routes to that container. If
versions match but a page still fails, capture the traceback from the logs
immediately after visiting that page. A successful HTTP 200 response alone is
insufficient: Solara renders the page later through its WebSocket connection.
