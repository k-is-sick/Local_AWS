FROM python:3.11-slim
WORKDIR /app
COPY app.py .
COPY templates/ templates/
RUN pip install flask flask-cors psycopg2-binary
EXPOSE 4566
CMD ["python", "app.py"]
