import json, logging, os, sqlite3, time
import pika
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
DB = os.getenv("DATABASE_PATH", "/tmp/notifications.db")
BROKER = os.getenv("BROKER_URL", "amqp://guest:guest@localhost:5672/")

def connect():
    c = sqlite3.connect(DB, timeout=15)
    c.execute("CREATE TABLE IF NOT EXISTS notifications (event_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, correlation_id TEXT NOT NULL, email TEXT NOT NULL)")
    c.commit()
    return c

def consume():
    with connect() as db:
        pass
    while True:
        try:
            conn = pika.BlockingConnection(pika.URLParameters(BROKER))
            ch = conn.channel()
            ch.exchange_declare(exchange="orders", exchange_type="fanout", durable=True)
            ch.queue_declare(queue="notifications", durable=True)
            ch.queue_bind(queue="notifications", exchange="orders")
            ch.basic_qos(prefetch_count=1)
            def handle(channel, method, properties, body):
                event = json.loads(body)
                with connect() as db:
                    cur = db.execute("INSERT OR IGNORE INTO notifications VALUES (?,?,?,?)", (event["event_id"], event["order_id"], event["correlation_id"], event["customer_email"]))
                    logging.info("event consumed correlation_id=%s event_id=%s duplicate=%s", event["correlation_id"], event["event_id"], cur.rowcount == 0)
                channel.basic_ack(delivery_tag=method.delivery_tag)
            ch.basic_consume(queue="notifications", on_message_callback=handle)
            logging.info("notification worker ready")
            ch.start_consuming()
        except Exception:
            logging.exception("consumer disconnected; retrying")
            time.sleep(3)

if __name__ == "__main__":
    consume()
