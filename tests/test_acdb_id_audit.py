"""ACDB first-column ID streaming audit, entirely synthetic offline fixtures."""
import gzip
from pathlib import Path
import tempfile
import unittest
from scripts.acdb_id_audit import inspect_ids, FirstColumnIDs


class ACDBIDAuditTests(unittest.TestCase):
    def fixture(self, body):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path=Path(tmp.name)/'test.sql.gz'
        with gzip.open(path,'wb') as stream:
            stream.write(body)
        return path

    def test_multiple_inserts_repeated_ids_and_string_escaping(self):
        source=self.fixture(b'''CREATE TABLE `characters` (
 `id` int NOT NULL,
 `romji` varchar(100)
) ENGINE=InnoDB;
INSERT INTO `characters` VALUES (1,'One, two (three)'),(2,'quote \\' escaped');
INSERT INTO `characters` VALUES (2,'same id'),(3,'many');
''')
        result=inspect_ids(source,'characters')
        self.assertEqual(result['inserted_tuples'],4)
        self.assertEqual(result['unique_first_column_ids'],3)
        self.assertEqual(result['repeated_first_column_ids'],1)
        self.assertEqual(result['image_rights_approved'],0)

    def test_giant_sql_string_fragmented_without_export(self):
        sql=(b'CREATE TABLE `characters` (\n `id` int,\n `romji` text\n);\n'
             +b'INSERT INTO `characters` VALUES (123,\''+b'Z'*200_000+b'');\n')
        # Construct valid SQL quotes even when giant field crosses fragment limits.
        sql=sql.replace(b"VALUES (123,'",b"VALUES (123,'")
        source=self.fixture(sql)
        result=inspect_ids(source,'characters')
        self.assertEqual(result['unique_first_column_ids'],1)
        self.assertEqual(result['inserted_tuples'],1)
        self.assertNotIn('Z'*100,str(result))

    def test_unknown_first_column_order_is_rejected(self):
        source=self.fixture(b'''CREATE TABLE `characters` (
 `name` text,
 `id` int
);
INSERT INTO `characters` VALUES ('Hero',1);
''')
        with self.assertRaises(ValueError):
            inspect_ids(source,'characters')

    def test_reject_unbounded_and_truncated(self):
        source=self.fixture(b'''CREATE TABLE `characters` (
 `id` int
);
INSERT INTO `characters` VALUES (1,'unfinished')
''')
        with self.assertRaises(ValueError):
            inspect_ids(source,'characters')
        with self.assertRaises(ValueError):
            inspect_ids(source,'characters',max_uncompressed_bytes=12)

    def test_parser_first_id_memory_bound(self):
        p=FirstColumnIDs(max_ids=1)
        with self.assertRaises(ValueError):
            p.feed(b"(1,'a'),(2,'b');")

    def test_assignments_first_column_requires_cid(self):
        src=self.fixture(b'''CREATE TABLE `assignments` (
 `cid` int,
 `pid` int
);
INSERT INTO `assignments` VALUES (12,55),(12,56),(13,55);
''')
        result=inspect_ids(src,'assignments')
        self.assertEqual(result['unique_first_column_ids'],2)
        self.assertEqual(result['inserted_tuples'],3)


if __name__=='__main__':
    unittest.main()
