# ── Stage 1: builder — cài dependencies vào thư mục riêng ──
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime — chỉ copy kết quả cần để chạy ──
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Cài vào /usr/local nên user non-root tìm thấy package mà không cần chỉnh PATH
COPY --from=builder /install /usr/local
COPY app ./app
COPY utils ./utils

RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:%s/health' % os.getenv('PORT', '8000'), timeout=3)"

# sh -c để đọc ${PORT}; exec để uvicorn thay thế sh, thành PID 1 và nhận SIGTERM.
# Thời gian chờ request dở dang (8s) ngắn hơn 10s mặc định của docker stop.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --timeout-graceful-shutdown 8"]
