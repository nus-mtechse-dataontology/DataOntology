# --- Stage 1: Builder ---
FROM public.ecr.aws/lambda/python:3.14 AS builder
WORKDIR /var/task
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN mkdir /install && uv pip install --system --target /install .

# --- Stage 2: Final Runner ---
FROM public.ecr.aws/lambda/python:3.14

# 1. Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

# 2. Copy dependencies
COPY --from=builder /install /var/lang/lib/python3.14/site-packages

# 3. Copy app code
COPY src/ ./src/
COPY resources/ ./resources/

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
    AWS_LWA_READINESS_CHECK_PATH="/actuator/health/liveness"

ENTRYPOINT []

# 6. The "Shield" CMD
# This loop specifically waits for the 200 OK from your actuator endpoint
CMD ["/bin/sh", "-c", "\
python -c \"from src.main import DataOntology; d=DataOntology(); d._load_config(); d._init_app(); import uvicorn; uvicorn.run(d._app, host='0.0.0.0', port=8000)\" & \
# Simple, one-line-compatible check
until python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/actuator/health/liveness', timeout=1)\" 2>/dev/null; do \
    echo 'Infra: Waiting for Actuator Health Check at /actuator/health/liveness...'; \
    sleep 1; \
done; \
echo 'Infra: Health Check Passed (200 OK).'; \
if [ -n \"$AWS_LAMBDA_RUNTIME_API\" ]; then \
    echo 'Infra: Lambda runtime detected. Starting Lambda Web Adapter.'; \
    exec /opt/extensions/lambda-adapter; \
else \
    echo 'Infra: Local runtime detected. Keeping Uvicorn process running.'; \
    wait; \
fi"]