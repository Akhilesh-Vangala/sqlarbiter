FROM python:3.11.17-slim AS dependencies
WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 VDIR_LOAD_DOTENV=0
COPY requirements-web.txt ./
COPY pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-web.txt

FROM dependencies AS test
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources
RUN python -m playwright install --with-deps chromium && chmod -R a+rX /opt/playwright
COPY src ./src
COPY investigator_runtime ./investigator_runtime
COPY tests ./tests
COPY data ./data
COPY scripts ./scripts
RUN mkdir -p artifacts/generated && chown -R 10001:10001 artifacts
USER 10001:10001
CMD ["sh", "scripts/container_checks.sh"]

FROM dependencies AS runtime
COPY src ./src
COPY investigator_runtime ./investigator_runtime
COPY data ./data
RUN mkdir -p /state && chown 10001:10001 /state
USER 10001:10001
ENV VDIR_STATE_DIR=/state VDIR_SQL_ENGINE=duckdb
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["python", "-m", "uvicorn", "vdir.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
