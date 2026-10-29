FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 app
COPY . .
USER 10001
CMD ["python", "workflow_engine.py"]
