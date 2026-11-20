FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements-validated.txt alembic.ini ./
COPY engine ./engine
COPY alembic ./alembic
COPY config ./config
COPY fixtures ./fixtures
COPY reports/p3-baselines.json ./reports/p3-baselines.json
RUN python -m pip install --no-cache-dir pip==26.3 && \
    python -m pip install --no-cache-dir -c requirements-validated.txt . && \
    useradd --uid 10001 --create-home engine
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "engine.serve"]
