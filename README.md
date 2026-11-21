# MaltaShop Microservices

Educational place-order prototype: Order REST API -> RabbitMQ -> Notification worker. Each service owns a separate SQLite database.

## Run
```bash
docker compose up --build
```
In another terminal:
```bash
curl -X POST http://localhost:8000/orders -H "Content-Type: application/json" -H "Idempotency-Key: order-001" -d '{"customer_email":"demo@example.com","item":"Notebook","quantity":2}'
docker compose logs order notification
```
The response includes an order ID and correlation ID. Search for the same correlation ID in both service logs. RabbitMQ management is on localhost:15672 (guest/guest for local development only).

## Configuration
- `BROKER_URL`: AMQP connection URL
- `DATABASE_PATH`: SQLite database location, distinct per service
- `PYTHONUNBUFFERED`: immediate logs

## Design
POST /orders atomically stores the order and an outbox event. A background publisher sends persistent `OrderPlaced` events to a durable RabbitMQ exchange. Notification stores processed event IDs to deduplicate redeliveries. Repeated HTTP requests with the same Idempotency-Key return the same order.

## Tests
```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```
GitHub Actions is configured to run these tests on push and pull request.

## Scope and limitations
This is a minimal educational prototype, **not** a complete Payment/Inventory saga. A production system needs compensating transactions, authentication, monitoring, migrations, and more robust messaging. The notification queue should be provisioned before any orders are placed, otherwise early fanout messages can be missed. A passing GitHub Actions run and screenshots must be checked against actual execution.
