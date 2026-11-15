# The public demo identity ships with the ANP examples; its private key is published,
# so it proves protocol mechanics only, never authority.
FROM alpine/git:2.47.2 AS source
ARG UPSTREAM=https://github.com/agent-network-protocol/anp-agent-example.git
ARG COMMIT=ddc141ed42746c582b02857f8519f1d6ae4a72d2
RUN git clone -q "$UPSTREAM" /src && git -C /src checkout -q "$COMMIT"

FROM python:3.12-slim
# Match the example agent's verifier (0.4.4). Newer clients sign with a payload
# that 0.4.4 rejects, which breaks the authenticated greet/echo demo.
RUN pip install --no-cache-dir "anp==0.4.4" "fastapi>=0.110" "uvicorn>=0.29"
RUN useradd --create-home --uid 10002 probe && mkdir -p /data && chown probe /data
COPY --from=source /src/docs/did_public /identity
COPY app.py /app/app.py
COPY fallback /app/fallback
USER probe
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
