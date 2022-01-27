FROM python:3.8-slim

WORKDIR /opt/AstroServerCheck

COPY requirements.txt ./

RUN apt-get update; \
    apt-get install -y --no-install-recommends curl; \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "./WebServer.py"]
