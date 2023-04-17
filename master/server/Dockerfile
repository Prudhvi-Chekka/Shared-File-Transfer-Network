FROM python:3

RUN mkdir /app
COPY . /app

RUN pip install sqlite3

WORKDIR /app

CMD ["python", "server.py"]