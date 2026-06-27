FROM python:3.12-slim

# build tools needed to compile pyswisseph's C extension (it builds its
# own internal libswe and sqlite3 from source, so it needs a compiler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
