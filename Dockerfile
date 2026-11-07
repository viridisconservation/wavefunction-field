# SPDX-License-Identifier: Apache-2.0
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    WF_DB_PATH=/data/field.sqlite3 WF_FIELD_KEY_FILE=/data/field.key
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home wf && mkdir /data && chown wf /data
USER wf
VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"
CMD ["wf-field", "serve", "--host", "0.0.0.0", "--port", "8080"]
