FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY graph_session.py .
COPY app.py .

ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
