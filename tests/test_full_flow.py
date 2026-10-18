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
        with psycopg.connect(cls.url) as db:
            with open('database/schema.sql',encoding='utf-8') as schema:
                db.execute(schema.read())

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


    def test_catch_ranking_survives_gift(self):
        with self.connect() as db:
            db.execute('UPDATE characters SET enabled=false WHERE id=ANY(%s)',(self.cids[1:],))
        spawned=storage.try_spawn(self.chat,1)
        caught=storage.claim(self.chat,701,spawned['name'])
        self.assertEqual(economy.leaderboard(chat_id=self.chat)[0]['owner_id'],701)
        self.assertTrue(economy.gift_card(701,702,caught['code']))
        self.assertEqual(storage.get_card(caught['code'])['owner_id'],702)
        self.assertEqual(economy.leaderboard(chat_id=self.chat)[0]['owner_id'],701)
        self.assertEqual(economy.leaderboard(today=True)[0]['owner_id'],701)

    def test_legacy_transferred_card_ranked_by_first_sender(self):
        with self.connect() as db:
            db.execute("""INSERT INTO owned_cards
                (code,character_id,owner_id,generation,caught_chat_id)
                VALUES ('LEGACYQA',%s,702,1,%s)""",(self.cids[0],self.chat))
            card_id=db.execute("SELECT id FROM owned_cards WHERE code='LEGACYQA'").fetchone()['id']
            db.execute("""INSERT INTO card_transfers
                (card_id,from_user_id,to_user_id,reason)
                VALUES (%s,701,702,'gift')""",(card_id,))
        result=economy.leaderboard(chat_id=self.chat)
        self.assertEqual(result[0]['owner_id'],701)


    def test_favorite_toggle_after_gift_cannot_edit_old_owner(self):
        with self.connect() as db:
            db.execute("""INSERT INTO owned_cards(code,character_id,owner_id,generation)
                VALUES ('FAVQA001',%s,701,1)""",(self.cids[0],))
        self.assertTrue(storage.toggle_favorite(701,'FAVQA001')['favorite'])
        self.assertFalse(storage.toggle_favorite(701,'FAVQA001')['favorite'])
        self.assertTrue(economy.gift_card(701,702,'FAVQA001'))
        self.assertIsNone(storage.toggle_favorite(701,'FAVQA001'))
        self.assertTrue(storage.toggle_favorite(702,'FAVQA001')['favorite'])

    def test_expired_spawn_clears_character_and_variant(self):
        with self.connect() as db:
            variant=db.execute("""INSERT INTO character_variants
                (character_id,variant_key,label,image_url)
                VALUES (%s,'expiry-test','Expiry Test','https://example.org/variant.png')
                RETURNING id""",(self.cids[0],)).fetchone()['id']
            db.execute("""INSERT INTO group_settings
                (chat_id,spawn_every,active_character_id,active_variant_id,last_spawn)
                VALUES (%s,35,%s,%s,now()-interval '16 minutes')""",
                (self.chat,self.cids[0],variant))
        self.assertIsNone(storage.claim(self.chat,701,'QA Character 0'))
        with self.connect() as db:
            row=db.execute("""SELECT active_character_id,active_variant_id
                FROM group_settings WHERE chat_id=%s""",(self.chat,)).fetchone()
        self.assertIsNone(row['active_character_id'])
        self.assertIsNone(row['active_variant_id'])
