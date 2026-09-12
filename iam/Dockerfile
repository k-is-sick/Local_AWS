FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY iam/ .
EXPOSE 4568
CMD ["python", "app.py"]