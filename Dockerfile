# --- Stage 1: Builder ---
FROM public.ecr.aws/lambda/python:3.14 AS builder
WORKDIR /var/task
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN mkdir /install && uv pip install --system --target /install .

# --- Stage 2: Final Runner ---
FROM public.ecr.aws/lambda/python:3.14

# SECURITY PATCH: Resolve glibc vulnerabilities (CVE-2026-4046)
# Amazon Linux 2023 requires dnf to pull the latest security updates.
# Force dnf to use a repository version that includes the glibc fix
RUN dnf clean all && \
    dnf update -y glibc --releasever 2023.11.20260427 && \
    dnf clean all

RUN rpm -q glibc

# 1. Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

# 2. Copy dependencies
COPY --from=builder /install /var/lang/lib/python3.14/site-packages

# 3. Copy app code
COPY src/ ./src/
COPY resources/ ./resources/
COPY datasets/ ./datasets/
COPY vault/ ./vault/

# 4. Pathing hack
RUN mkdir -p home/default && ln -s /var/task/resources /var/task/home/default/resources

# 5. INFRA FIX: Environment Setup
ENV PROJECT_PATH=/var/task \
    PYTHONPATH=/var/task:/var/task/src \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    AWS_LWA_PORT=8000 \
    AWS_LWA_ASYNC_INIT=true \
    AWS_LAMBDA_FUNCTION_NAME="local-testing" \
    AWS_LWA_READINESS_CHECK_PATH="/actuator/health/liveness"\
    GRAPHDB_URL="http://172.31.43.149:7200/repositories/dataontology"
ENTRYPOINT []

# Lambda Web Adapter runs as extension automatically; run web app process directly.
CMD ["/bin/sh", "-c", "set -e; mkdir -p /tmp/project/resources /tmp/project/vault; cp -r /var/task/resources/. /tmp/project/resources/; cp /var/task/vault/* /tmp/project/vault/; if [ -n \"$DB_USER\" ]; then printf \"%s\" \"$DB_USER\" > /tmp/project/vault/postgres.user; fi; if [ -n \"$DB_PASSWORD\" ]; then printf \"%s\" \"$DB_PASSWORD\" > /tmp/project/vault/postgres.password; fi; if [ -n \"$DB_HOST\" ]; then sed -i \"s|host = \\\"localhost\\\"|host = \\\"$DB_HOST\\\"|g\" /tmp/project/resources/config.toml; fi; if [ -n \"$DB_PORT\" ]; then sed -i \"s|port = 5432|port = $DB_PORT|g\" /tmp/project/resources/config.toml; fi; if [ -n \"$DB_NAME\" ]; then sed -i \"s|name = \\\"data_ontology\\\"|name = \\\"$DB_NAME\\\"|g\" /tmp/project/resources/config.toml; fi; export PROJECT_PATH=/tmp/project; python -c \"from src.main import DataOntology; d=DataOntology(); d._load_config(); d._init_app(); import uvicorn; uvicorn.run(d._app, host='0.0.0.0', port=8000)\""]