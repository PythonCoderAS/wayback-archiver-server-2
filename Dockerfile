FROM python:3.12-slim as generate-requirements

# Path: /app
WORKDIR /app

COPY ./Pipfile ./Pipfile.lock ./
RUN ["pip", "install", "pipenv"]
RUN ["sh", "-c", "pipenv requirements --dev > requirements.txt"]

FROM python:3.12-slim as build

# Path: /app
WORKDIR /app

# Path: /app/requirements.txt
COPY --from=generate-requirements /app/requirements.txt ./

RUN ["pip", "install", "-r", "requirements.txt"]

COPY src .

ENTRYPOINT [ "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers" ]

EXPOSE 8000