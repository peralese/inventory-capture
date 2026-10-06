import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import db


class SearchPagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(db, 'DB_PATH', Path(self.temp.name) / 'test.db')
        self.path_patch.start()
        db.init_db()
        self.conn = db.get_connection()
        rows = [
            ('Cobalt blue vase', 'Glass', 'Shelf A', 'In Stock', 'chip on rim'),
            ('Brass candlestick', 'Metal', 'Bin 3', 'Sold', None),
            ('Blue willow plate', 'China', 'Shelf B', 'Listed', '100% original'),
            ('Pocket watch', 'Metal', 'Safe', 'In Stock', 'needs_service'),
        ]
        for name, category, location, status, notes in rows:
            db.create_item(self.conn, dict(name=name, category=category, storage_location=location,
                                           availability_status=status, notes=notes))
        for i in range(60):
            db.create_item(self.conn, dict(name=f'Filler {i}', storage_location='Box', availability_status='Kept'))

    def tearDown(self):
        self.conn.close()
        self.path_patch.stop()
        self.temp.cleanup()

    def names(self, **kwargs):
        return [row['name'] for row in db.list_items(self.conn, **kwargs)]

    def test_search_matches_any_field_case_insensitively(self):
        self.assertEqual(self.names(search='BLUE'), ['Cobalt blue vase', 'Blue willow plate'])
        self.assertEqual(self.names(search='bin 3'), ['Brass candlestick'])
        self.assertEqual(self.names(search='metal'), ['Brass candlestick', 'Pocket watch'])
        self.assertEqual(self.names(search='chip'), ['Cobalt blue vase'])
        self.assertEqual(self.names(search='0004'), ['Pocket watch'])

    def test_search_words_all_must_match_and_combine_with_filters(self):
        self.assertEqual(self.names(search='blue china shelf'), ['Blue willow plate'])
        self.assertEqual(self.names(search='blue', availability_status='In Stock'), ['Cobalt blue vase'])
        self.assertEqual(self.names(search='metal', storage_location='Safe'), ['Pocket watch'])

    def test_like_wildcards_are_literal(self):
        self.assertEqual(self.names(search='100%'), ['Blue willow plate'])
        self.assertEqual(self.names(search='needs_'), ['Pocket watch'])
        self.assertEqual(self.names(search='%'), ['Blue willow plate'])

    def test_paging_counts_and_positions(self):
        self.assertEqual(db.count_items(self.conn), 64)
        self.assertEqual(db.count_items(self.conn, search='filler'), 60)
        page2 = db.list_items(self.conn, limit=25, offset=25)
        self.assertEqual([r['item_id'] for r in page2][:2], ['0026', '0027'])
        self.assertEqual(len(db.list_items(self.conn, limit=25, offset=50)), 14)
        self.assertEqual(db.item_position(self.conn, '0064'), 63)
        self.assertEqual(db.item_position(self.conn, '0002', search='blue'), None)
        self.assertEqual(db.item_position(self.conn, '0003', search='blue'), 1)

    def test_list_view_pages_and_preserves_state(self):
        main = importlib.import_module('app.main')
        render = MagicMock()
        with patch.object(main.templates, 'TemplateResponse', render):
            main.list_view(MagicMock(), q='  filler ', page='9', per_page='25')
            ctx = render.call_args[0][1]
            self.assertEqual((ctx['q'], ctx['page'], ctx['page_count'], ctx['total']), ('filler', 3, 3, 60))
            self.assertEqual((ctx['first_shown'], ctx['last_shown']), (51, 60))
            self.assertEqual(ctx['page_url'](2), '/?q=filler&page=2&per_page=25')

            main.list_view(MagicMock(), highlight='0064')
            ctx = render.call_args[0][1]
            self.assertEqual((ctx['page'], ctx['per_page']), (2, 50))

            main.list_view(MagicMock(), per_page='9999', page='abc')
            ctx = render.call_args[0][1]
            self.assertEqual((ctx['page'], ctx['per_page']), (1, 50))

        html = main.templates.get_template('index.html').render(dict(ctx, request=MagicMock()))
        self.assertIn('Showing 1&ndash;50 of 64 items', html)
        self.assertIn('href="/?page=2"', html)

    def test_quick_update_returns_to_same_search_and_page(self):
        main = importlib.import_module('app.main')
        response = main.quick_update('0001', availability_status='Reserved', storage_location=None,
                                     return_status='', return_location='Shelf A & B', return_q='blue vase',
                                     return_page='2', return_per_page='25')
        self.assertEqual(response.headers['location'],
                         '/?storage_location=Shelf+A+%26+B&q=blue+vase&page=2&per_page=25')
        self.assertEqual(db.get_item(self.conn, '0001')['availability_status'], 'Reserved')


if __name__ == '__main__':
    unittest.main()
