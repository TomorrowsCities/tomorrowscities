FROM python:3.10

RUN useradd -m -u 1000 user

#USER root
RUN apt update
RUN apt -y install gdal-bin libgdal-dev git-lfs

USER user

ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

COPY --chown=user . $HOME/app

WORKDIR $HOME/app

RUN pip install -e .

# Fail the build if the resolved runtime cannot even start Solara's CLI.
RUN SOLARA_TELEMETRY_MIXPANEL_ENABLE=false python -m solara run --help > /dev/null

CMD ["solara", "run", "tomorrowcities.pages", "--production", "--workers", "1", "--host", "0.0.0.0", "--port", "7860"]
