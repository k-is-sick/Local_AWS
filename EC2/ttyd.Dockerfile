FROM tsl0922/ttyd:latest
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*