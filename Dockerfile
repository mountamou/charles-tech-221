FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY serve.py ./serve.py
RUN mkdir -p app/uploads
EXPOSE 8000
CMD ["python", "serve.py"]
