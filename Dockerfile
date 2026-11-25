FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --system alerts \
    && useradd --system --gid alerts alerts \
    && install -d -o alerts -g alerts /app/data

COPY bot/ ./bot/
USER alerts

CMD ["python", "-m", "bot.main"]
