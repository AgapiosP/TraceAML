FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN groupadd --gid 10001 traceaml && useradd --uid 10001 --gid 10001 --no-create-home traceaml
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
RUN python -m pip install --no-cache-dir --no-deps .
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"]
CMD ["traceaml", "serve", "--host", "0.0.0.0", "--port", "8000"]
