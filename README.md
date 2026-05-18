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

## Sample Data
[tcdse_sample_data](https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view)
