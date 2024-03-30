FROM python:3.8-alpine

ADD requirements.txt .
ADD exporter.py .
ADD start.sh .
RUN pip install -r requirements.txt

ENV IP=""
ARG IP

ENTRYPOINT [ "./start.sh" ]
CMD [ "${IP}" ]