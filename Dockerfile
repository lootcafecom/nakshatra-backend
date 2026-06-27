FROM python:3.12-slim

# build tools needed to compile pyswisseph's C/C++ extension:
# gcc + libc6-dev compile the C files, g++ compiles one C++ file (swhdbxx.cpp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
