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
        weak = self.client.post("/flex/register", data={
            "business_name": "مغسلة ضعيفة", "full_name": "مالك",
            "phone_prefix": "00972", "phone": "599999999", "password": "weakpass1",
        })
        self.assertEqual(weak.status_code, 302)
        with self.module.db() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) count FROM businesses").fetchone()["count"], 0)
        registered = self.client.post("/flex/register", data={
            "business_name": "مغسلة الاختبار",
            "full_name": "مالك المغسلة",
            "phone_prefix": "00972",
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
        self.assertIn('id="service-quantity"'.encode(), dashboard.data)
        self.assertIn('id="service-note"'.encode(), dashboard.data)
        self.assertIn('id="live-order-total"'.encode(), dashboard.data)
        self.assertIn("زبون جديد".encode(), dashboard.data)
        with self.module.db() as connection:
            self.assertEqual(connection.execute("SELECT phone FROM users WHERE id=1").fetchone()["phone"], "+972599000011")
            sweater = connection.execute("SELECT id FROM services WHERE business_id=1 AND name='كنزة / سويتر'").fetchone()
            shirt_treatments = connection.execute("SELECT treatment FROM services WHERE business_id=1 AND name='قميص'").fetchall()
            iron_shirt = connection.execute("SELECT id FROM services WHERE business_id=1 AND name='قميص' AND treatment='كوي فقط'").fetchone()
        self.assertIsNotNone(sweater)
        self.assertEqual({row["treatment"] for row in shirt_treatments}, {"غسيل وكوي", "غسيل فقط", "كوي فقط", "تنظيف جاف"})
        customer_response = self.client.post("/flex/customers", data={
            "name": "زبون اختبار كامل أول", "phone_prefix": "+970", "phone": "599111000", "address": "رام الله، المصيون",
        })
        self.assertEqual(customer_response.status_code, 302)
        with self.module.db() as connection:
            catalog_customer = connection.execute("SELECT id FROM customers WHERE display_phone='+970599111000'").fetchone()
        order = self.client.post("/flex/orders", data={
            "customer_id": str(catalog_customer["id"]), "customer_name": "زبون اختبار كامل أول", "customer_phone": "+970599111000",
            "item_type[]": "catalog", "service_id[]": str(iron_shirt["id"]),
            "manual_name[]": "", "item_treatment[]": "كوي فقط", "item_unit[]": "قطعة",
            "item_price[]": "4.4", "item_note[]": "", "save_manual[]": "0", "quantity[]": "2",
            "discount": "0", "paid": "0",
        })
        self.assertEqual(order.status_code, 302)
        with self.module.db() as connection:
            saved_item = connection.execute("SELECT service_name FROM order_items ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(saved_item["service_name"], "قميص — كوي فقط")
        self.assertEqual(self.client.get("/flex/health").json["app"], "FLEX")
        self.client.post("/flex/logout")
        login = self.client.post("/flex/login?next=/", data={
            "phone_prefix": "00972", "phone": "0599000011", "password": "StrongPass123",
        })
        self.assertEqual(login.status_code, 302)
        self.assertTrue(login.headers["Location"].endswith("/flex/"))

    def test_create_order_with_manual_service(self):
        self.client.post("/flex/register", data={
            "business_name": "Manual Test",
            "full_name": "Owner",
            "phone": "0599000022",
            "password": "StrongPass123",
        })
        self.client.post("/flex/customers", data={
            "name": "Customer Full Four Name", "phone_prefix": "+970", "phone": "599111222", "address": "Ramallah",
        })
        with self.module.db() as connection:
            customer_id = connection.execute("SELECT id FROM customers WHERE display_phone='+970599111222'").fetchone()["id"]
        response = self.client.post("/flex/orders", data={
            "customer_id": str(customer_id),
            "customer_name": "Customer",
            "customer_phone": "+970599111222",
            "item_type[]": "manual",
            "service_id[]": "",
            "manual_name[]": "Special item",
            "item_unit[]": "قطعة",
            "item_price[]": "17.5",
            "item_note[]": "Handle carefully",
            "save_manual[]": "1",
            "quantity[]": "2.4",
            "discount": "0",
            "paid": "0",
        })
        self.assertEqual(response.status_code, 302)
        with self.module.db() as connection:
            item = connection.execute("SELECT * FROM order_items ORDER BY id DESC LIMIT 1").fetchone()
            saved = connection.execute("SELECT * FROM services WHERE name='Special item'").fetchone()
        self.assertEqual(item["line_total"], 35)
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["item_note"], "Handle carefully")
        self.assertIsNotNone(saved)

        lookup = self.client.get("/flex/api/customers?q=Customer")
        self.assertEqual(lookup.status_code, 200)
        customer = lookup.json["customers"][0]
        self.assertEqual(customer["open_count"], 1)
        self.assertEqual(customer["orders"][0]["status"], "مستلم")

        second = self.client.post("/flex/orders", data={
            "customer_id": str(customer["id"]),
            "customer_name": "Customer",
            "customer_phone": "+970599111222",
            "item_type[]": "manual",
            "service_id[]": "",
            "manual_name[]": "Second item",
            "item_unit[]": "كيلو",
            "item_price[]": "10",
            "item_note[]": "",
            "save_manual[]": "0",
            "quantity[]": "1.5",
            "discount": "0",
            "paid": "0",
        })
        self.assertEqual(second.status_code, 302)
        with self.module.db() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) count FROM customers").fetchone()["count"], 1)
            weighted = connection.execute("SELECT * FROM order_items ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(weighted["quantity"], 1.5)
        self.assertEqual(weighted["line_total"], 15)


if __name__ == "__main__":
    unittest.main()
