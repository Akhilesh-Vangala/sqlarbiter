FROM python:3.12-slim AS dependencies
WORKDIR /app
ENV PYTHONPATH=/app/backend/src PYTHONDONTWRITEBYTECODE=1 VDIR_LOAD_DOTENV=0
COPY backend/requirements/runtime.txt ./backend/requirements/
COPY pyproject.toml ./
RUN pip install --no-cache-dir -r backend/requirements/runtime.txt

FROM dependencies AS dbt_tooling
COPY backend/requirements/dbt.txt ./backend/requirements/
RUN python -m venv /opt/dbt && /opt/dbt/bin/python -m pip install --no-cache-dir -r backend/requirements/dbt.txt
ENV VDIR_DBT_EXECUTABLE=/opt/dbt/bin/dbt

FROM dbt_tooling AS test
COPY backend/requirements/development.txt ./backend/requirements/
RUN pip install --no-cache-dir -r backend/requirements/development.txt
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources
RUN python -m playwright install --with-deps chromium && chmod -R a+rX /opt/playwright
COPY backend/src ./backend/src
COPY frontend ./frontend
COPY agent/investigator ./agent/investigator
COPY backend/tests ./backend/tests
COPY backend/data ./backend/data
COPY backend/dbt ./backend/dbt
COPY scripts ./scripts
RUN mkdir -p artifacts/generated && chown -R 10001:10001 artifacts
USER 10001:10001
CMD ["sh", "scripts/checks/container_checks.sh"]

FROM dbt_tooling AS runtime
COPY backend/src ./backend/src
COPY frontend ./frontend
COPY agent/investigator ./agent/investigator
COPY backend/data ./backend/data
COPY backend/dbt ./backend/dbt
RUN mkdir -p /state && chown 10001:10001 /state
USER 10001:10001
ENV VDIR_STATE_DIR=/state VDIR_SQL_ENGINE=duckdb
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["python", "-m", "uvicorn", "vdir.api.routes:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
