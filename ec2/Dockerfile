FROM python:3.11-slim
WORKDIR /app
COPY shared/ shared/
COPY ec2/ .
RUN pip install flask docker requests
EXPOSE 4567
CMD ["python", "app.py"]