# --- Stage 1: Builder ---
FROM public.ecr.aws/lambda/python:3.14 AS builder

WORKDIR /var/task

# Install uv for fast dependency resolution
RUN pip install uv

# Copy only dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock ./

# Install dependencies into a specific folder
# --prefix /install tells uv to put everything in one spot
RUN mkdir /install && uv pip install --system --target /install .

# --- Stage 2: Final Runner ---
FROM public.ecr.aws/lambda/python:3.14

# 1. Add the Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /var/task

# 2. Copy ONLY the installed packages from the builder
COPY --from=builder /install /var/lang/lib/python3.14/site-packages

# 3. Copy application code and resources
COPY src/ ./src/
COPY resources/ ./resources/

# 4. HOT-FIX: Force 0.0.0.0 in config
RUN sed -i 's/127.0.0.1/0.0.0.0/g' resources/config.toml

# 5. Environment Variables
ENV PROJECT_PATH=/var/task \
    PYTHONPATH=/var/task/src \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    AWS_LWA_PORT=8000

# 6. Mirror the pathing hack
RUN mkdir -p home/default && ln -s /var/task/resources /var/task/home/default/resources

ENTRYPOINT []

# 7. Start the app
CMD ["/var/lang/bin/python", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]