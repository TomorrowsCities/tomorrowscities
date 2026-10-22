---
title: App Engine
emoji: 🏆
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
---

[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/TomorrowsCities/tomorrowscities.git)

## Installation
* Make sure your operating system has [GDAL](https://gdal.org/) installed.
* Make sure you use Python > 3.8
~~~bash
git clone https://github.com/TomorrowsCities/tomorrowcities
cd tomorrowcities
pip install -e .
solara run tomorrowcities.pages
~~~

### Development setup note
Use `pip install -e .` for local development. It installs dependencies from
`pyproject.toml` and installs this repository as an editable package, so
`solara run tomorrowcities.pages` can import `tomorrowcities` correctly.

`pip install -r requirements.txt` only installs listed dependencies and does
not install this project package itself unless explicitly included.

### Docker updates and UI compatibility

The UI uses Vue 2 / Vuetify 2 components and custom templates. Keep the tested
versions in `pyproject.toml` and `requirements.txt`: Solara 1.44.1, ipyvue 1.11.2,
ipyvuetify 1.11.1 and Reacton 1.9.1. The matching server stack is Uvicorn 0.34.0,
Starlette 0.46.0 and websockets 15.0. An unconstrained rebuild can select the newer Vue/Vuetify
widget stack, causing missing-component errors on Compute/Explore and different
header styling. See [deployment troubleshooting](docs/deployment_troubleshooting.md)
for the rebuild and verification commands.

## Sample Data

For analysis sessions without development reloads, start with:

~~~bash
solara run tomorrowcities.pages --production --workers 1
~~~

Impact inputs are read sequentially through temporary files. Tables and charts
are prepared when their panels are opened; exports are generated on demand.
See [upload troubleshooting](docs/upload_troubleshooting.md) for limits and
server disconnect diagnostics. Restart/redeploy the app after updating its code.

Flood depth inputs must be in metres; convert raw GIRI centimetre data before
upload. The default flood casualty metric uses a provisional, configurable
scenario model. Review the in-app Flood and Metrics
documentation and Calculation Parameters; defaults are not local calibration.
Use `legacy-depth` for comparison with the previous corrected application baseline.

[tcdse_sample_data](https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view)
