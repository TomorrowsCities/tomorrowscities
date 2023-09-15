FROM python:3.9

RUN useradd -m -u 1000 user

USER user

ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

COPY --chown=user . $HOME/app

WORKDIR $HOME/app

COPY ./requirements.txt $HOME/app/requirements.txt

#RUN sudo apt -y install gdal-bin libgdal-dev

RUN pip install --no-cache-dir --upgrade -r $HOME/app/requirements.txt

COPY . .

CMD ["solara", "run", "app_engine.py", "--host", "0.0.0.0", "--port", "7860"]

