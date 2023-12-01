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

COPY src/main.py src/main.py
COPY dump_openapi.py .
ENV FASTAPI_OPENAPI_OUTPUT="/tmp/openapi.json"
RUN ["mkdir", "-p", "frontend/dist"]
RUN ["python3", "dump_openapi.py"]

FROM node:20 as build-frontend

# Path: /tmp/
WORKDIR /tmp/

COPY ./frontend frontend
WORKDIR /tmp/frontend
RUN ["npm", "install"]
COPY --from=build-server /tmp/openapi.json /tmp/openapi.json
RUN ["npx", "openapi-typescript", "/tmp/openapi.json", "-o", "src/api/schema.d.ts"]
RUN ["npm", "run", "build"]

FROM python:3.12-slim as production
COPY --from=build-server /venv /venv
COPY src/main.py .
COPY --from=build-frontend /tmp/frontend/dist ./frontend/dist
ENV PATH="/venv/bin:$PATH"

ENTRYPOINT [ "python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers" ]

EXPOSE 8000