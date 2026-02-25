FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY convert_bpmn.py .
COPY app.py .

EXPOSE 9998

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9998"]
