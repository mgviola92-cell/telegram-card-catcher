import gzip
import tempfile
import unittest
from pathlib import Path
from scripts.inspect_acdb_dumps import summarize_file

class ACDBDumpInspectionTests(unittest.TestCase):
    def test_reads_gz_inserts_without_assuming_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'characters.sql.gz'
            with gzip.open(path,'wt',encoding='utf-8') as out:
                out.write('CREATE TABLE `characters` (id INT);\n')
                out.write("INSERT INTO `characters` VALUES (1),(2);\n")
                out.write("INSERT INTO `characters` VALUES (3);\n")
            result=summarize_file(path)
            self.assertEqual(result['inserts_by_table'],{'characters':2})
            self.assertEqual(result['create_statements_by_table'],{'characters':1})
            self.assertEqual(result['insert_statements'],2)

    def test_rejects_uncompressed_input(self):
        with self.assertRaises(ValueError):
            summarize_file('characters.sql')
