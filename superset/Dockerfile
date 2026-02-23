FROM apache/superset:latest

USER root
COPY start.sh /start.sh
RUN chmod +x /start.sh
USER superset

ENTRYPOINT ["/start.sh"]
