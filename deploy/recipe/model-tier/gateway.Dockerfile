# Feature 017: container image of the tenant gateway for sites that run it in a container (a production option).
# On Omniverse2 the gateway runs as a host user unit (tenant-gateway.service). Build from the repository root:
#   docker build -f deploy/recipe/model-tier/gateway.Dockerfile -t forge-model-tier-gateway .
# The image holds only the factory-agnostic model_tier package and its runtime dependencies; no factory code.
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
RUN useradd --create-home --uid 10001 tier
WORKDIR /opt/model-tier
COPY factory/python/model_tier ./model_tier
RUN pip install --no-cache-dir "fastapi==0.143.1" "uvicorn==0.54.0" "httpx==0.28.1" "pyyaml==6.0.3" "jsonschema==4.26.0"
USER tier
EXPOSE 18480
ENTRYPOINT ["python", "-m", "model_tier.tenant_gateway"]
