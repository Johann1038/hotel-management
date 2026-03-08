FROM python:3.13-slim

WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ /app/frontend/

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "hotel.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
