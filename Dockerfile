FROM python:3.12 as generate-requirements

# Path: /app
WORKDIR /app

COPY ./Pipfile ./Pipfile.lock ./
RUN ["pip", "install", "pipenv"]
RUN ["sh", "-c", "pipenv requirements --dev > requirements.txt"]
RUN ["rm", "Pipfile", "Pipfile.lock"]

FROM python:3.12 as build-server-deps

# Path: /app
WORKDIR /app

# Path: /app/requirements.txt
COPY --from=generate-requirements /app/requirements.txt ./
RUN ["python3", "-m", "venv", "/venv"]
ENV PATH="/venv/bin:$PATH"
RUN ["python3", "-m", "pip", "install", "-r", "requirements.txt"]

FROM node:20 as build-frontend-deps

# Path: /tmp/
WORKDIR /tmp/

COPY ./frontend/package.json frontend/package.json
WORKDIR /tmp/frontend
RUN ["npm", "install"]

FROM python:3.12 as build-server-openapi

WORKDIR /app

COPY --from=build-server-deps /venv /venv

COPY src src
COPY dump_openapi.py .
ENV FASTAPI_OPENAPI_OUTPUT="/tmp/openapi.json"
RUN ["mkdir", "-p", "frontend/dist"]

ENV PATH="/venv/bin:$PATH"
RUN ["python3", "dump_openapi.py"]

FROM node:20 as build-frontend

COPY --from=build-server-openapi /tmp/openapi.json /tmp/openapi.json
COPY ./frontend /tmp/frontend
COPY --from=build-frontend-deps /tmp/frontend/node_modules /tmp/frontend/node_modules

WORKDIR /tmp/frontend

RUN ["npx", "openapi-typescript", "/tmp/openapi.json", "-o", "src/api/schema.d.ts"]

ARG SENTRY_AUTH_TOKEN=""
ENV SENTRY_AUTH_TOKEN=${SENTRY_AUTH_TOKEN}
RUN ["npm", "run", "build"]

FROM python:3.12-slim-bookworm as production

ARG S6_OVERLAY_VERSION=3.1.6.2

RUN apt update && apt install -y wget xz-utils
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp/
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz
RUN cd /tmp/ && wget -q https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-$(uname -m).tar.xz
RUN tar -C / -Jxpf /tmp/s6-overlay-$(uname -m).tar.xz
COPY ./s6 /etc/s6-overlay/s6-rc.d/

ENV S6_KEEP_ENV=1
ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2
ENV S6_VERBOSITY=1

WORKDIR /app

COPY src ./src
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY --from=build-server-deps /venv /venv
COPY --from=build-frontend /tmp/frontend/dist ./frontend/dist
ENV PATH="/venv/bin:$PATH"

CMD [ "python3", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers" ]

EXPOSE 8000

ENTRYPOINT [ "/init" ]
