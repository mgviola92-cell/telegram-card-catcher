"""End-to-end data path using disposable PostgreSQL, no Telegram API calls."""
import unittest
from unittest.mock import patch
import psycopg
from psycopg.rows import dict_row
from tests.test_db_integration import safe_test_database_url
from app import storage, economy, trading

class FullFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=safe_test_database_url()
        if not cls.url: raise unittest.SkipTest('TEST_DATABASE_URL missing')

    def connect(self):
        return psycopg.connect(self.url,row_factory=dict_row)

    def setUp(self):
        self.patches=[patch('app.storage.connect',self.connect),
                      patch('app.economy.connect',self.connect),
                      patch('app.trading.connect',self.connect)]
        for p in self.patches:p.start()
        self.chat=-98765001
        self.cids=[]
        with self.connect() as db:
            db.execute('DELETE FROM group_settings WHERE chat_id=%s',(self.chat,))
            for i in range(2):
                row=db.execute("""INSERT INTO characters
                  (name,series,source_key,image_url,weight)
                  VALUES (%s,'Integration','qa:fullflow:'||%s,
                          'https://example.org/qa.jpg',100)
                  RETURNING id""",(f'QA Character {i}',str(i)+'-'+str(__import__('time').time_ns()))).fetchone()
                self.cids.append(row['id'])

    def tearDown(self):
        with self.connect() as db:
            db.execute('DELETE FROM trade_offers WHERE sender_id IN (701,702) OR receiver_id IN (701,702)')
            db.execute('DELETE FROM card_transfers WHERE from_user_id IN (701,702) OR to_user_id IN (701,702)')
            db.execute('DELETE FROM owned_cards WHERE character_id=ANY(%s)',(self.cids,))
            db.execute('DELETE FROM group_settings WHERE chat_id=%s',(self.chat,))
            db.execute('DELETE FROM character_variants WHERE character_id=ANY(%s)',(self.cids,))
            db.execute('DELETE FROM characters WHERE id=ANY(%s)',(self.cids,))
        for p in reversed(self.patches):p.stop()

    def test_spawn_catch_harem_gift(self):
        # Test catalog contains precisely one eligible character during spawn.
        with self.connect() as db:
            db.execute('UPDATE characters SET enabled=false WHERE id=ANY(%s)',(self.cids[1:],))
        char=storage.try_spawn(self.chat,1)
        self.assertIsNotNone(char)
        self.assertEqual(storage.claim(self.chat,701,'incorrect'),None)
        caught=storage.claim(self.chat,701,char['name'])
        self.assertIsNotNone(caught)
        self.assertEqual(storage.claim(self.chat,702,char['name']),None)
        cards,total=storage.get_cards(701)
        self.assertEqual(total,1)
        self.assertEqual(cards[0]['code'],caught['code'])
        self.assertTrue(economy.gift_card(701,702,caught['code']))
        self.assertEqual(storage.get_cards(701)[1],0)
        self.assertEqual(storage.get_cards(702)[1],1)
        self.assertFalse(economy.gift_card(701,702,caught['code']))

    def test_trade_accept_once_and_audit(self):
        with self.connect() as db:
            for i,cid in enumerate(self.cids):
                db.execute("""INSERT INTO owned_cards
                   (code,character_id,owner_id,generation)
                   VALUES (%s,%s,%s,1)""",(f'QAFT{i}',cid,701+i))
        offer=trading.create_offer(701,702,'QAFT0','QAFT1')
        self.assertIsInstance(offer,int)
        self.assertFalse(trading.finish_offer(offer,701,True))
        self.assertTrue(trading.finish_offer(offer,702,True))
        self.assertFalse(trading.finish_offer(offer,702,True))
        self.assertEqual(storage.get_card('QAFT0')['owner_id'],702)
        self.assertEqual(storage.get_card('QAFT1')['owner_id'],701)
        with self.connect() as db:
            audit=db.execute("""SELECT count(*) AS n FROM card_transfers
               WHERE from_user_id IN (701,702) AND reason='trade'""").fetchone()
            self.assertEqual(audit['n'],2)
