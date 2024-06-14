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



RUN (cd tomorrowcities & pip install -e .)

CMD ["solara", "run", "tomorrowcities.pages",  "--host", "0.0.0.0", "--port", "7860"]
#COPY ./requirements.txt $HOME/app/requirements.txt



#RUN pip install --no-cache-dir --upgrade -r $HOME/app/requirements.txt

#COPY . .

#CMD ["solara", "run", "app_engine.py", "--host", "0.0.0.0", "--port", "7860"]

