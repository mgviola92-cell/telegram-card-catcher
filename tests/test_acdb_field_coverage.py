"""Synthetic-only, rights-safe ACDB field coverage aggregation tests."""
import gzip
from pathlib import Path
import tempfile
import unittest

from scripts.acdb_field_coverage import inspect_coverage


class ACDBCoverageTests(unittest.TestCase):
    def dump(self, table, columns, statements):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest=Path(tmp.name)/(table+'.sql.gz')
        ddl='CREATE TABLE `'+table+'` (\n'
        ddl+='\n'.join(' `'+col+'` text,' for col in columns)+'\n) ENGINE=InnoDB;\n'
        with gzip.open(dest,'wb') as file:
            file.write((ddl+statements).encode('utf8'))
        return dest

    def test_coverage_counts_nonblank_name_and_artwork_hints(self):
        cols=['id','romji','japanese','image','thumb','trait']
        src=self.dump('characters',cols,
          """INSERT INTO `characters` VALUES
(1,'Hero',NULL,'abc.jpg',NULL,'x'),
(2,'','日本語',NULL,'thumb.png','y'),
(3,NULL,NULL,NULL,NULL,'z'),
(4,'Character (special), one',NULL,'',NULL,'w');
INSERT INTO `characters` VALUES
(5,'Name with \\' quotation',NULL,'image_name',NULL,'a');\n""")
        r=inspect_coverage(src,'characters')
        self.assertEqual(r['sql_rows'],5)
        self.assertEqual(r['characters_with_name_hint'],4)
        self.assertEqual(r['characters_with_artwork_pointer_hint'],3)
        self.assertEqual(r['characters_with_both_hints'],3)
        self.assertEqual(r['nonblank_field_counts']['romji'],3)
        self.assertEqual(r['nonblank_field_counts']['japanese'],1)
        self.assertEqual(r['nonblank_field_counts']['image'],2)
        self.assertEqual(r['nonblank_field_counts']['thumb'],1)
        self.assertEqual(r['image_urls_verified'],0)
        self.assertEqual(r['image_rights_approved'],0)
        self.assertNotIn('abc.jpg',str(r))
        self.assertNotIn('日本語',str(r))

    def test_title_source_no_images(self):
        src=self.dump('publishers',['id','english','japanese','romjititle'],
             "INSERT INTO `publishers` VALUES (1,'Title',NULL,NULL),(2,NULL,NULL,'Romaji'),(3,'',NULL,NULL);\n")
        r=inspect_coverage(src,'publishers')
        self.assertEqual(r['sql_rows'],3)
        self.assertEqual(r['titles_with_name_hint'],2)
        self.assertEqual(r['characters_with_artwork_pointer_hint'],0)

    def test_reject_schema_without_artwork_fields_and_truncated_dump(self):
        src=self.dump('characters',['id','romji','japanese','image'],
                      "INSERT INTO `characters` VALUES (1,'a',NULL,'x');\n")
        with self.assertRaises(ValueError):
            inspect_coverage(src,'characters')
        src2=self.dump('characters',['id','romji','japanese','image','thumb'],
                       "INSERT INTO `characters` VALUES (1,'a',NULL,'x','y')")
        with self.assertRaises(ValueError):
            inspect_coverage(src2,'characters')

    def test_row_column_mismatch_and_giant_quoted_field(self):
        src=self.dump('characters',['id','romji','japanese','image','thumb'],
                       "INSERT INTO `characters` VALUES (1,'a',NULL,'x');\n")
        with self.assertRaises(ValueError):
            inspect_coverage(src,'characters')
        src2=self.dump('characters',['id','romji','japanese','image','thumb'],
                       "INSERT INTO `characters` VALUES (1,'"
                       +('Y'*180_000)+"',NULL,'x',NULL);\n")
        r=inspect_coverage(src2,'characters')
        self.assertEqual(r['sql_rows'],1)
        self.assertEqual(r['characters_with_both_hints'],1)
        self.assertNotIn('Y'*100,str(r))

    def test_limits_and_safety(self):
        src=self.dump('publishers',['id','english','japanese','romjititle'],
                      "INSERT INTO `publishers` VALUES (1,'x',NULL,NULL);\n")
        with self.assertRaises(ValueError):
            inspect_coverage(src,'publishers',max_uncompressed_bytes=10)
        with self.assertRaises(ValueError):
            inspect_coverage(src,'unknown')
        with self.assertRaises(ValueError):
            inspect_coverage(src,'publishers',max_uncompressed_bytes=True)


if __name__=='__main__':
    unittest.main()
