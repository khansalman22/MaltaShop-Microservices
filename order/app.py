import json, logging, os, sqlite3, time, uuid, threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
import pika

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
DB = os.getenv("DATABASE_PATH", "/tmp/orders.db")
BROKER = os.getenv("BROKER_URL", "amqp://guest:guest@localhost:5672/")

def connect():
    c = sqlite3.connect(DB, timeout=15)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, customer_email TEXT NOT NULL, item TEXT NOT NULL, quantity INTEGER NOT NULL, correlation_id TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, payload TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0)")
    c.commit()
    return c

def create_order(email, item, quantity, key):
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT id, correlation_id FROM orders WHERE key=?", (key,)).fetchone()
        if row:
            return {"order_id": row[0], "correlation_id": row[1], "status": "accepted", "duplicate": True}
        oid, cid, eid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        payload = json.dumps({"event_id": eid, "event_type": "OrderPlaced", "order_id": oid, "correlation_id": cid, "customer_email": email, "item": item, "quantity": quantity})
        c.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)", (oid, key, email, item, quantity, cid))
        c.execute("INSERT INTO outbox (id,payload) VALUES (?,?)", (eid, payload))
        logging.info("order accepted correlation_id=%s order_id=%s", cid, oid)
        return {"order_id": oid, "correlation_id": cid, "status": "accepted", "duplicate": False}

def publish_loop():
    while True:
        try:
            conn = pika.BlockingConnection(pika.URLParameters(BROKER))
            channel = conn.channel()
            channel.exchange_declare(exchange="orders", exchange_type="fanout", durable=True)
            channel.confirm_delivery()
            while True:
                with connect() as db:
                    rows = db.execute("SELECT id,payload FROM outbox WHERE published=0 ORDER BY rowid LIMIT 25").fetchall()
                for eid, payload in rows:
                    channel.basic_publish(exchange="orders", routing_key="", body=payload.encode(), properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"), mandatory=False)
                    with connect() as db:
                        db.execute("UPDATE outbox SET published=1 WHERE id=?", (eid,))
                    logging.info("event published correlation_id=%s event_id=%s", json.loads(payload)["correlation_id"], eid)
                time.sleep(0.5)
        except Exception:
            logging.exception("publisher disconnected; retrying")
            time.sleep(3)

@asynccontextmanager
async def lifespan(app):
    connect().close()
    threading.Thread(target=publish_loop, daemon=True).start()
    yield

app = FastAPI(title="MaltaShop Order API", lifespan=lifespan)

class OrderInput(BaseModel):
    customer_email: str = Field(min_length=3)
    item: str = Field(min_length=1)
    quantity: int = Field(gt=0)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/orders", status_code=202)
def place_order(order: OrderInput, idempotency_key: str | None = Header(default=None)):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    return create_order(order.customer_email, order.item, order.quantity, idempotency_key)
