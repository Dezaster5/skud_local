FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements /app/requirements
RUN pip install --upgrade pip && pip install -r /app/requirements/base.txt

COPY . /app
RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["gunicorn", "skud_local.wsgi:application", "--bind", "0.0.0.0:8000"]

