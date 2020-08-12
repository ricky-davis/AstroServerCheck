FROM python:3.7-slim

WORKDIR /opt/AstroServerCheck

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "./WebServer.py"]
