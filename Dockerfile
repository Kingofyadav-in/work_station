FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       curl \
       build-essential \
       python3-dev \
       portaudio19-dev \
       procps \
       bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt ./

RUN pip install --upgrade pip \
    && pip install -r requirements.lock.txt

COPY . .

EXPOSE 5050 8501

CMD ["bash", "scripts/start_all.sh"]