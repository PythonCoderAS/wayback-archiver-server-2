FROM python:3.12 as generate-requirements

# Path: /app
WORKDIR /app

COPY ./Pipfile ./Pipfile.lock ./
RUN ["pip", "install", "pipenv"]
RUN ["sh", "-c", "pipenv requirements --dev > requirements.txt"]
RUN ["rm", "Pipfile", "Pipfile.lock"]

FROM python:3.12 as build-server

# Path: /app
WORKDIR /app

# Path: /app/requirements.txt
COPY --from=generate-requirements /app/requirements.txt ./
RUN ["python3", "-m", "venv", "/venv"]
ENV PATH="/venv/bin:$PATH"
RUN ["python3", "-m", "pip", "install", "-r", "requirements.txt"]

FROM node:20 as build-frontend

# Path: /tmp/
WORKDIR /tmp/

COPY ./frontend .
RUN ["npm", "install"]
RUN ["npm", "run", "build"]

FROM python:3.12-slim as production
COPY --from=build-server /venv /venv
COPY src/main.py .
COPY --from=build-frontend /tmp/dist ./frontend/dist
ENV PATH="/venv/bin:$PATH"

ENTRYPOINT [ "python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers" ]

EXPOSE 8000