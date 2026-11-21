FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
FROM python:3.12-slim
COPY --from=build /install /usr/local
WORKDIR /app
COPY order/ ./order/
RUN useradd --system --uid 10001 app && mkdir /data && chown app /data
USER app
EXPOSE 8000
CMD ["uvicorn", "order.app:app", "--host", "0.0.0.0", "--port", "8000"]
