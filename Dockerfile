FROM python:3.11-slim

WORKDIR /app

COPY evoting/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY evoting/ ./evoting/
COPY evoting/app.py .

RUN mkdir -p /app/data /app/evoting/static/uploads

ENV PYTHONPATH=/app
ENV DATABASE_URL=sqlite:////app/data/evoting.db

EXPOSE 5000

CMD ["python", "evoting/app.py"]
