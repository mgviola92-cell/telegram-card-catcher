"""Numeric ID owner lookup and favorite mutations, with mocked DB only."""
import unittest
from unittest.mock import MagicMock, patch

from app import storage


class NumericStorageTests(unittest.TestCase):
    def connect(self, row=None, rows=None):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value=row
        cursor=db.cursor.return_value.__enter__.return_value
        cursor.execute.return_value=cursor
        cursor.fetchall.return_value=rows or []
        return db,cursor

    def test_check_numeric_id_uses_primary_key(self):
        db,_=self.connect(row={'card_id':6103, 'code':'40QBIWXI8P'})
        with patch('app.storage.connect') as mocked:
            mocked.return_value.__enter__.return_value=db
            result=storage.get_card("6103")
        self.assertEqual(result['card_id'],6103)
        query,args=db.execute.call_args.args
        self.assertIn("o.id=%s",query)
        self.assertNotIn("WHERE o.code=%s",query)
        self.assertEqual(args,(6103,))

    def test_old_alphanumeric_id_still_works(self):
        db,_=self.connect(row={'card_id':6103, 'code':'40QBIWXI8P'})
        with patch('app.storage.connect') as mocked:
            mocked.return_value.__enter__.return_value=db
            result=storage.get_card("40qbiwxi8p")
        self.assertIsNotNone(result)
        query,args=db.execute.call_args.args
        self.assertIn("WHERE o.code=%s",query)
        self.assertEqual(args,('40QBIWXI8P',))

    def test_bad_references_do_not_connect(self):
        with patch('app.storage.connect') as mocked:
            self.assertIsNone(storage.get_card("1;delete"))
            self.assertIsNone(storage.get_card("0"))
        mocked.assert_not_called()

    def test_numeric_favorite_only_changes_card_of_requesting_owner(self):
        db,cursor=self.connect(rows=[{'id':6103,'code':'40QBIWXI8P'}])
        with patch('app.storage.connect') as mocked:
            mocked.return_value.__enter__.return_value=db
            self.assertEqual(storage.set_favorites(345,[6103],True),1)
        first=cursor.execute.call_args_list[0].args
        last=cursor.execute.call_args_list[1].args
        self.assertIn('owner_id=%s',first[0])
        self.assertEqual(first[1],(345,[6103],[]))
        self.assertIn('id=ANY(%s)',last[0])
        self.assertEqual(last[1],(True,345,[6103]))

    def test_old_code_favorite_remains_valid(self):
        db,cursor=self.connect(rows=[{'id':6103,'code':'40QBIWXI8P'}])
        with patch('app.storage.connect') as mocked:
            mocked.return_value.__enter__.return_value=db
            changed=storage.set_favorites(345,['40qbiwxi8p'],False)
        self.assertEqual(changed,1)
        self.assertEqual(cursor.execute.call_args_list[0].args[1],
                         (345,[],['40QBIWXI8P']))

    def test_wrong_owner_no_favorite_changes(self):
        db,cursor=self.connect(rows=[])
        with patch('app.storage.connect') as mocked:
            mocked.return_value.__enter__.return_value=db
            result=storage.set_favorites(345,['6103'],True)
        self.assertEqual(result,0)
        self.assertEqual(cursor.execute.call_count,1)

    def test_mixed_codes_atomic_and_deduplicated(self):
        db,cursor=self.connect(rows=[{'id':6103,'code':'40QBIWXI8P'},
                                      {'id':6104,'code':'DB2ABC1234'}])
        with patch('app.storage.connect') as mocked:
            mocked.return_value.__enter__.return_value=db
            result=storage.set_favorites(345,['6103','db2abc1234'],True)
        self.assertEqual(result,2)
        self.assertEqual(set(cursor.execute.call_args_list[1].args[1][2]),
                         {6103,6104})


if __name__ == '__main__':
    unittest.main()
