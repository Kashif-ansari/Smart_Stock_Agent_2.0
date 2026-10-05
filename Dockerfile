FROM python:3.12-slim
ARG INSTALL_AI=true
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    AUTO_WORKER=false STORAGE_PATH=/app/data APP_ENV=production \
    OTEL_SDK_DISABLED=true CREWAI_TRACING_ENABLED=false
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements*.txt ./
RUN python -m pip install --upgrade pip \
    && if [ "$INSTALL_AI" = "true" ]; then pip install -r requirements-ai.txt; else pip install -r requirements.txt; fi
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
COPY --chown=app:app . .
RUN mkdir -p /app/data && chown -R app:app /app/data
USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=3)"
CMD ["sh","-c","python -m alembic upgrade head && python -m streamlit run app.py --server.address=0.0.0.0"]
