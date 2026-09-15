FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ shared/
COPY s3/ s3/
COPY dynamodb/ dynamodb/
COPY templates/ templates/
COPY static/ static/
COPY app.py .
EXPOSE 4566
CMD ["python", "app.py"]
