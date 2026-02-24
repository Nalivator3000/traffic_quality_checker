FROM apache/superset:latest

USER root
COPY start.sh /start.sh
RUN chmod +x /start.sh && \
    mkdir -p /app/pythonpath && \
    chown -R superset:superset /app/pythonpath && \
    /app/.venv/bin/python3 -m pip install --quiet psycopg2-binary
USER superset

ENTRYPOINT ["/start.sh"]
