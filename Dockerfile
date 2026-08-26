FROM python:3.12-alpine

WORKDIR /app

# pymodbus 3.7.x leaks one listening socket per closed connection, so a client
# that reconnects turns into thousands of stale listeners and every new connect
# gets progressively more expensive. Fixed in 3.8. Do not move to 3.9+ without
# code changes: ModbusSlaveContext was renamed there.
RUN pip install --no-cache-dir "pymodbus==3.8.*" "pyyaml>=6.0"

COPY sim/ ./sim/

EXPOSE 1502

CMD ["python", "-m", "sim.server"]
