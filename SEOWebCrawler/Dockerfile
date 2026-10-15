FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements-server.txt requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements-server.txt
COPY pyproject.toml README.md ./
COPY seowebcrawler ./seowebcrawler
RUN pip install --no-deps . && \
    useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app

USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "180", "seowebcrawler.web:create_app()"]