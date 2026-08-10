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
        login_page = self.client.get("/flex/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn(b'data-flex-install', login_page.data)
        manifest = self.client.get("/flex/static/manifest.webmanifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.json["start_url"], "/flex/")
        self.assertEqual(manifest.json["scope"], "/flex/")
        icon_sizes = {icon["sizes"] for icon in manifest.json["icons"]}
        self.assertIn("192x192", icon_sizes)
        self.assertIn("512x512", icon_sizes)
        manifest.close()
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
        self.assertTrue(registered.headers["Location"].endswith("/flex/subscription"))
        subscription_page = self.client.get("/flex/subscription")
        self.assertIn("بانتظار التفعيل".encode(), subscription_page.data)
        with self.module.db() as connection:
            created_business = connection.execute("SELECT subscription_status,setup_paid FROM businesses WHERE id=1").fetchone()
            self.assertEqual(created_business["subscription_status"], "pending")
            self.assertEqual(created_business["setup_paid"], 0)
            connection.execute("UPDATE businesses SET subscription_status='active',subscription_end='2027-08-10T12:00' WHERE id=1")
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
        closing_date = self.module.today()
        with self.module.db() as connection:
            order_id = connection.execute("SELECT id FROM orders ORDER BY id DESC LIMIT 1").fetchone()["id"]
            connection.execute(
                "INSERT INTO payments(business_id,order_id,amount,payment_method,paid_at) VALUES(?,?,?,?,?)",
                (1, order_id, 80, "نقدي", f"{closing_date} 10:00:00"),
            )
            connection.execute(
                "INSERT INTO payments(business_id,order_id,amount,payment_method,paid_at) VALUES(?,?,?,?,?)",
                (1, order_id, 20, "بطاقة", f"{closing_date} 11:00:00"),
            )
            connection.execute(
                "INSERT INTO expenses(business_id,expense_date,category,amount,note) VALUES(?,?,?,?,?)",
                (1, closing_date, "مواد تنظيف", 30, "Daily closing test"),
            )
        closing_page = self.client.get(f"/flex/cash-accounts?date={closing_date}")
        self.assertEqual(closing_page.status_code, 200)
        self.assertIn(b'href="/flex/cash-accounts"', closing_page.data)
        self.assertIn('مقبوضات غير نقدية'.encode(), closing_page.data)
        self.assertIn('id="cash-closing-form"'.encode(), closing_page.data)
        self.assertIn('data-cash-received="80.0"'.encode(), closing_page.data)
        closed = self.client.post("/flex/cash/close", data={
            "closing_date": closing_date, "opening_cash": "10", "actual_cash": "61", "note": "Counted",
        })
        self.assertEqual(closed.status_code, 302)
        with self.module.db() as connection:
            cash_day = connection.execute("SELECT * FROM cash_days WHERE business_id=1 AND closing_date=?", (closing_date,)).fetchone()
        self.assertEqual(cash_day["total_received"], 100)
        self.assertEqual(cash_day["cash_received"], 80)
        self.assertEqual(cash_day["non_cash_received"], 20)
        self.assertEqual(cash_day["expense_total"], 30)
        self.assertEqual(cash_day["expected_cash"], 60)
        self.assertEqual(cash_day["cash_difference"], 1)
        with self.module.db() as connection:
            connection.execute(
                "INSERT INTO expenses(business_id,expense_date,category,amount,note) VALUES(?,?,?,?,?)",
                (1, closing_date, "مواد تنظيف", 6, "Added after closing"),
            )
        stale_closing = self.client.get(f"/flex/cash-accounts?date={closing_date}")
        self.assertIn("الحركة تغيّرت بعد الإقفال".encode(), stale_closing.data)
        self.assertIn("إعادة عدّ الكاش وتحديث الإقفال".encode(), stale_closing.data)
        self.assertIn("7.00".encode(), stale_closing.data)
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
        with self.module.db() as connection:
            connection.execute("UPDATE businesses SET subscription_status='active',subscription_end='2027-08-10T12:00'")
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
        order_page = self.client.get(response.headers["Location"])
        self.assertIn("تعديل الفاتورة".encode(), order_page.data)
        self.assertIn('id="invoice-edit-list"'.encode(), order_page.data)
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
            latest_order = connection.execute("SELECT id FROM orders ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(weighted["quantity"], 1.5)
        self.assertEqual(weighted["line_total"], 15)

        edited = self.client.post(f"/flex/orders/{latest_order['id']}/edit", data={
            "item_name[]": "Edited item", "quantity[]": "3", "unit[]": "قطعة",
            "unit_price[]": "7", "item_note[]": "Updated", "discount": "1",
            "due_date": "2026-08-12T10:00", "notes": "Invoice edited",
        })
        self.assertEqual(edited.status_code, 302)
        with self.module.db() as connection:
            edited_order = connection.execute("SELECT * FROM orders WHERE id=?", (latest_order["id"],)).fetchone()
            edited_item = connection.execute("SELECT * FROM order_items WHERE order_id=?", (latest_order["id"],)).fetchone()
        self.assertEqual(edited_order["subtotal"], 21)
        self.assertEqual(edited_order["total"], 20)
        self.assertEqual(edited_order["due_date"], "2026-08-12T10:00")
        self.assertEqual(edited_item["service_name"], "Edited item")
        self.assertEqual(edited_item["item_note"], "Updated")

        due_date_change = self.client.post(
            f"/flex/orders/{latest_order['id']}/due-date",
            data={"due_day": "14", "due_month": "8", "due_year": "2026", "due_time": "15:30"},
        )
        self.assertEqual(due_date_change.status_code, 302)
        with self.module.db() as connection:
            changed_due_date = connection.execute(
                "SELECT due_date FROM orders WHERE id=?", (latest_order["id"],)
            ).fetchone()["due_date"]
        self.assertEqual(changed_due_date, "2026-08-14T15:30")

        order_page = self.client.get(f"/flex/orders/{latest_order['id']}")
        self.assertIn(b'/due-date', order_page.data)
        self.assertIn(b'name="due_day" type="number" min="1" max="31" value="14"', order_page.data)
        self.assertIn(b'name="due_month" type="number" min="1" max="12" value="08"', order_page.data)
        self.assertIn(b'name="due_year" type="number" min="2026" max="2100" value="2026"', order_page.data)
        self.assertIn(b'class="print-delivery"', order_page.data)
        self.assertIn(b'14/08/2026', order_page.data)
        self.assertIn(b'class="print-footer"', order_page.data)

        with self.module.db() as connection:
            connection.execute(
                "INSERT INTO expenses(business_id,expense_date,category,amount,note) VALUES(?,?,?,?,?)",
                (1, "2026-08-10", "مواد", 25, "Deletion test"),
            )
            deleted = self.module.delete_business_account(connection, 1)
            self.assertEqual(deleted, 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM businesses").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users WHERE business_id=1").fetchone()[0], 0)
            for table in ("orders", "customers", "expenses", "order_items", "payments"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM services WHERE business_id=1").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
