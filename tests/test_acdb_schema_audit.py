"""ACDB schema inspector synthetic fixture tests; no network, no image fetching."""
import gzip
from pathlib import Path
import tempfile
import unittest
from scripts.acdb_schema_audit import inspect_file


class ACDBSchemaAuditTests(unittest.TestCase):
    def create_dump(self, content):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        dest = Path(folder.name) / 'characters.sql.gz'
        with gzip.open(dest, 'wb') as out:
            out.write(content)
        return dest

    def test_realistic_mysql_dump_schema_and_statement_counts(self):
        src = self.create_dump(b'''-- metadata
CREATE TABLE IF NOT EXISTS `characters` (
 `id` int(11) NOT NULL,
 `name` varchar(255) NOT NULL,
 `image` varchar(255) DEFAULT NULL,
 PRIMARY KEY (`id`)
) ENGINE=InnoDB;
INSERT INTO `characters` VALUES (1,'name'),(2,'name');
INSERT INTO `characters` VALUES (3,'name');
CREATE TABLE `assignments` (
 `char_id` int(11),
 `title_id` int(11)
) ENGINE=InnoDB;
''')
        result = inspect_file(src)
        self.assertEqual(result['create_statements_by_table'], {'assignments':1,'characters':1})
        self.assertEqual(result['columns_by_table']['characters'], ['id','name','image'])
        self.assertEqual(result['columns_by_table']['assignments'], ['char_id','title_id'])
        self.assertEqual(result['insert_statements_by_table']['characters'], 2)
        self.assertEqual(result['compressed_bytes'], src.stat().st_size)
        self.assertEqual(len(result['compressed_sha256']), 64)
        self.assertTrue(result['character_rows_measured'])
        self.assertEqual(result['inserted_tuples_by_table']['characters'], 3)
        self.assertEqual(result['rights_approved_artworks'], 0)

    def test_giant_sql_line_cannot_be_accidentally_emitted(self):
        src = self.create_dump(b"INSERT INTO `characters` VALUES (1,'" + b'X'*150_000 + b"');\n")
        result = inspect_file(src)
        self.assertEqual(result['insert_statements_by_table'], {'characters':1})
        self.assertEqual(result['overlong_sql_lines_skipped'], 1)
        self.assertEqual(result['inserted_tuples_by_table']['characters'], 1)
        self.assertNotIn('X'*100, str(result))

    def test_decompression_limit_and_missing_gz(self):
        src = self.create_dump(b'A'*100)
        with self.assertRaises(ValueError):
            inspect_file(src,max_uncompressed_bytes=12)
        with self.assertRaises(ValueError):
            inspect_file('data.sql')

    def test_empty_dump(self):
        src=self.create_dump(b'')
        self.assertEqual(inspect_file(src)['uncompressed_bytes'],0)


if __name__ == '__main__':
    unittest.main()
