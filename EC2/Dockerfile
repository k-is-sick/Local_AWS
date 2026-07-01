FROM python:3.11-slim
WORKDIR /app
COPY app.py .
COPY ttyd.Dockerfile .
RUN pip install flask docker
EXPOSE 4567
CMD ["python", "app.py"]