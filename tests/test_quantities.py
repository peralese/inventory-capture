import importlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db


class QuantityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(db, 'DB_PATH', Path(self.temp.name) / 'test.db')
        self.path_patch.start()
        db.init_db()
        self.conn = db.get_connection()

    def tearDown(self):
        self.conn.close()
        self.path_patch.stop()
        self.temp.cleanup()

    def test_legacy_migration_is_idempotent(self):
        self.conn.execute('DROP TABLE items')
        self.conn.execute(db.SCHEMA)
        for item_id, status in [('0001', 'In Stock'), ('0002', 'Listed'), ('0003', 'Sold')]:
            self.conn.execute('INSERT INTO items (item_id, name, availability_status) VALUES (?, ?, ?)', (item_id, 'Copies', status))
        db._migrate(self.conn)
        self.assertEqual([tuple(row) for row in self.conn.execute('SELECT quantity_on_hand, quantity_listed, quantity_sold FROM items ORDER BY item_id')], [(1, 0, 0), (1, 1, 0), (0, 0, 1)])
        self.conn.execute('UPDATE items SET quantity_on_hand = 5 WHERE item_id = "0001"')
        db._migrate(self.conn)
        self.assertEqual(db.get_item(self.conn, '0001')['quantity_on_hand'], 5)

    def test_partial_sale_and_zero_counts_persist(self):
        data = dict(name='Copies', availability_status='Listed', quantity_on_hand=5, quantity_listed=2, quantity_sold=0)
        item_id = db.create_item(self.conn, data)
        data.update(quantity_on_hand=4, quantity_listed=1, quantity_sold=1)
        db.update_item(self.conn, item_id, data)
        self.assertEqual(db.get_item(self.conn, item_id)['quantity_on_hand'], 4)
        data.update(quantity_on_hand=0, quantity_listed=0, quantity_sold=5)
        db.update_item(self.conn, item_id, data)
        self.assertEqual(db.get_item(self.conn, item_id)['quantity_on_hand'], 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute('UPDATE items SET quantity_sold = -1')

    def test_form_validation_and_new_item_error_action(self):
        main = importlib.import_module('app.main')
        data = {field: '' for field in ['name', 'category', 'storage_location', 'condition', 'photo_on_file', 'notes', 'acquired_date', 'acquired_from', 'acquisition_cost', 'listed', 'listing_platform', 'listing_price', 'listing_date', 'sold_date', 'sold_price', 'fees_shipping_cost', 'net_profit', 'final_disposition']}
        data.update(name='Copies', availability_status='In Stock', quantity_on_hand='5', quantity_listed='2', quantity_sold='0')
        parsed, error = main._build_item_data(**data)
        self.assertIsNone(error)
        self.assertEqual(parsed['quantity_on_hand'], 5)
        for invalid in ['-1', '1.5', 'abc', '']:
            _, error = main._build_item_data(**dict(data, quantity_sold=invalid))
            self.assertIsNotNone(error)
        parsed, error = main._build_item_data(**dict(data, quantity_listed='6'))
        self.assertIn('cannot exceed', error)
        html = main.templates.get_template('item_form.html').render(item=parsed, error=error, statuses=db.ALLOWED_STATUSES)
        self.assertIn('action="/items/new"', html)


if __name__ == '__main__':
    unittest.main()
