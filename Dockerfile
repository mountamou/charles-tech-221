FROM python:3.12-slim
WORKDIR /app

# Fetch the litestream binary straight from GitHub releases (checksum verified) instead of
# pulling a second base image from Docker Hub, which is prone to anonymous pull rate limits
# in shared CI build environments.
ARG LITESTREAM_VERSION=0.5.17
ARG LITESTREAM_SHA256=cfb371176d164437ae869f8351cfde49bd1804ae71c61923f75c9cba9c9c006d
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL -o /tmp/litestream.tar.gz \
      "https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-linux-x86_64.tar.gz" && \
    echo "${LITESTREAM_SHA256}  /tmp/litestream.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin litestream && \
    rm /tmp/litestream.tar.gz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY serve.py ./serve.py
COPY litestream.yml /etc/litestream.yml
COPY start.sh ./start.sh
RUN mkdir -p app/uploads /data && chmod +x start.sh
ENV DATABASE_URL=sqlite:////data/charlestech.db
EXPOSE 8000
CMD ["./start.sh"]
