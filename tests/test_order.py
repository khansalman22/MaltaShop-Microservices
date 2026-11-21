import os, tempfile, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

class OrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.dict(os.environ, {"DATABASE_PATH": self.tmp.name + "/orders.db"})
        self.patch.start()
        import order.app as module
        self.module = module
        self.original = module.DB
        module.DB = os.environ["DATABASE_PATH"]
        module.connect().close()

    def tearDown(self):
        self.module.DB = self.original
        self.patch.stop()
        self.tmp.cleanup()

    def test_idempotent_order(self):
        first = self.module.create_order("a@example.com", "Book", 1, "key-1")
        second = self.module.create_order("a@example.com", "Book", 1, "key-1")
        self.assertEqual(first["order_id"], second["order_id"])
        self.assertTrue(second["duplicate"])
        with self.module.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 1)

    def test_distinct_keys(self):
        a = self.module.create_order("a@example.com", "Book", 1, "key-a")
        b = self.module.create_order("a@example.com", "Book", 1, "key-b")
        self.assertNotEqual(a["order_id"], b["order_id"])

if __name__ == "__main__":
    unittest.main()
