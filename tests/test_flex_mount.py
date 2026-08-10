import importlib
import os
import sys
import tempfile
import unittest

from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.test import Client
from werkzeug.wrappers import Response


class FlexMountedAppTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLEX_DB_PATH"] = os.path.join(self.temp_dir.name, "flex.db")
        sys.modules.pop("flex_dryclean.app", None)
        module = importlib.import_module("flex_dryclean.app")
        self.module = module
        parent = Flask("test-parent")
        mounted = DispatcherMiddleware(parent, {"/flex": module.app})
        self.client = Client(mounted, Response, use_cookies=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_register_login_assets_and_isolation_mount(self):
        self.assertEqual(self.client.get("/flex/login").status_code, 200)
        asset = self.client.get("/flex/static/flex-app-icon.png")
        self.assertEqual(asset.status_code, 200)
        asset.close()
        registered = self.client.post("/flex/register", data={
            "business_name": "مغسلة الاختبار",
            "full_name": "مالك المغسلة",
            "phone": "0599000011",
            "password": "StrongPass123",
        })
        self.assertEqual(registered.status_code, 302)
        self.assertTrue(registered.headers["Location"].endswith("/flex/settings/business"))
        dashboard = self.client.get("/flex/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"/flex/static/app.css", dashboard.data)
        self.assertIn('id="service-category"'.encode(), dashboard.data)
        self.assertIn('id="manual-service-form"'.encode(), dashboard.data)
        self.assertEqual(self.client.get("/flex/health").json["app"], "FLEX")

    def test_create_order_with_manual_service(self):
        self.client.post("/flex/register", data={
            "business_name": "Manual Test",
            "full_name": "Owner",
            "phone": "0599000022",
            "password": "StrongPass123",
        })
        response = self.client.post("/flex/orders", data={
            "customer_name": "Customer",
            "customer_phone": "0599111222",
            "item_type[]": "manual",
            "service_id[]": "",
            "manual_name[]": "Special item",
            "item_unit[]": "قطعة",
            "item_price[]": "17.5",
            "save_manual[]": "1",
            "quantity[]": "2",
            "discount": "0",
            "paid": "0",
        })
        self.assertEqual(response.status_code, 302)
        with self.module.db() as connection:
            item = connection.execute("SELECT * FROM order_items ORDER BY id DESC LIMIT 1").fetchone()
            saved = connection.execute("SELECT * FROM services WHERE name='Special item'").fetchone()
        self.assertEqual(item["line_total"], 35)
        self.assertIsNotNone(saved)


if __name__ == "__main__":
    unittest.main()
