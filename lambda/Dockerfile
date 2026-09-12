FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ shared/
COPY lambda/ lambda/
COPY app.py .
EXPOSE 4569
CMD ["python", "lambda/app.py"]
