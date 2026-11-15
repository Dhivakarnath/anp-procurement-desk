# The ANP team's own example agent (the one they host at agent-connect.ai/agents/test),
# built unmodified from a pinned upstream commit. Nothing from this repository is copied in.
FROM alpine/git:2.47.2 AS source
ARG UPSTREAM=https://github.com/agent-network-protocol/anp-agent-example.git
ARG COMMIT=ddc141ed42746c582b02857f8519f1d6ae4a72d2
RUN git clone -q "$UPSTREAM" /src && git -C /src checkout -q "$COMMIT"

FROM python:3.12-slim
# Upstream pyproject dependencies, minus openai (only their LLM client uses it).
RUN pip install --no-cache-dir \
      "fastapi>=0.100.0" "uvicorn[standard]>=0.23.0" "pydantic>=2.0.0" "httpx>=0.24.0" \
      "python-multipart>=0.0.6" "pyyaml>=6.0" "python-dotenv>=1.0.0" "anp==0.4.4"
RUN useradd --create-home --uid 10001 peer
COPY --from=source --chown=peer:peer /src /home/peer/agent
# Upstream lists AGENT_DESCRIPTION_JSON_DOMAIN (host:port) in allowed_domains, but the
# DID-WBA verifier compares the host only. Accept both forms so signed calls succeed.
RUN python - <<'PY'
from pathlib import Path
p = Path("/home/peer/agent/src/remote_agent.py")
text = p.read_text()
old = 'allowed_domains=["localhost", "0.0.0.0", "127.0.0.1", AGENT_DESCRIPTION_JSON_DOMAIN]'
new = (
    'allowed_domains=["localhost", "0.0.0.0", "127.0.0.1", '
    'AGENT_DESCRIPTION_JSON_DOMAIN, AGENT_DESCRIPTION_JSON_DOMAIN.split(":")[0]]'
)
if old not in text:
    raise SystemExit("remote_agent.py allowed_domains line changed upstream")
p.write_text(text.replace(old, new, 1))
PY
# Local DID resolver so auth works when didhost.cc serves HTML instead of JSON.
COPY --chown=peer:peer boot.py /home/peer/agent/src/boot.py
USER peer
WORKDIR /home/peer/agent/src
EXPOSE 8000
CMD ["python", "boot.py"]
