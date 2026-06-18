FROM python:3.11-slim

WORKDIR /app

# Standard pip install.
RUN pip install pymodbus==3.5.2

COPY slave.py .

# CMD is overridden by the docker-compose.yml file
CMD ["python", "--version"]
