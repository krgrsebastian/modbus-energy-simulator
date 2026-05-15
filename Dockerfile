FROM python:3.12-alpine

WORKDIR /app

RUN pip install --no-cache-dir "pymodbus==3.7.*" "pyyaml>=6.0"

COPY sim/ ./sim/

EXPOSE 1502

CMD ["python", "-m", "sim.server"]
