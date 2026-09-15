FROM python:3.12-slim
WORKDIR /app
COPY --from=litestream/litestream:0.5.17 /usr/local/bin/litestream /usr/local/bin/litestream
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
