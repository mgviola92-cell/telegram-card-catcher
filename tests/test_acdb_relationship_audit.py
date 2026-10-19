"""Synthetic-only ACDB relationship audit tests; no network, no Neon, no media."""
import gzip
from pathlib import Path
import tempfile
import unittest
from scripts.acdb_relationship_audit import AssignmentRelations, inspect_relationships


def fixture(folder, table, cols, rows):
    dest=folder/(table+'.sql.gz')
    schema='CREATE TABLE `'+table+'` (\n'+'\n'.join(' `'+c+'` int,' for c in cols)+'\n) ENGINE=InnoDB;\n'
    values='INSERT INTO `'+table+'` VALUES '+','.join('('+','.join(str(v) for v in row)+')' for row in rows)+';\n'
    with gzip.open(dest,'wb') as f:
        f.write((schema+values).encode('utf8'))
    return dest


class RelationshipAuditTests(unittest.TestCase):
    def sources(self, chars=(1,2,3), titles=(10,20),
                pairs=((1,10),(1,20),(2,10),(2,10),(999,10),(3,777))):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder=Path(tmp.name)
        character=fixture(folder,'characters',['id','other'],[(n,1) for n in chars])
        publisher=fixture(folder,'publishers',['id','other'],[(n,1) for n in titles])
        assignment=fixture(folder,'assignments',['cid','pid'],pairs)
        return character,publisher,assignment

    def test_realistic_references_and_repeated_pairs(self):
        result=inspect_relationships(*self.sources())
        self.assertEqual(result['unique_character_ids'],3)
        self.assertEqual(result['unique_title_ids'],2)
        self.assertEqual(result['assignment_rows'],6)
        self.assertEqual(result['unique_assignment_pairs'],5)
        self.assertEqual(result['repeated_assignment_pairs'],1)
        self.assertEqual(result['assignments_with_missing_characters'],1)
        self.assertEqual(result['assignments_with_missing_titles'],1)
        self.assertEqual(result['distinct_missing_character_ids'],1)
        self.assertEqual(result['distinct_missing_title_ids'],1)
        self.assertEqual(result['characters_with_valid_title'],2)
        self.assertEqual(result['titles_with_valid_character'],2)
        self.assertEqual(result['characters_without_valid_title'],1)
        self.assertEqual(result['titles_without_valid_character'],0)
        self.assertFalse(result['all_references_valid'])
        self.assertEqual(result['approved_artworks'],0)
        self.assertEqual(result['images_downloaded'],0)
        self.assertNotIn('999',str(result))
        self.assertNotIn('777',str(result))

    def test_perfect_relation_and_many_to_many(self):
        r=inspect_relationships(*self.sources(chars=(1,2),titles=(7,8),
                                              pairs=((1,7),(1,8),(2,8))))
        self.assertTrue(r['all_references_valid'])
        self.assertEqual(r['characters_without_valid_title'],0)
        self.assertEqual(r['titles_without_valid_character'],0)
        self.assertEqual(r['unique_assignment_pairs'],3)

    def test_wrong_ddl_is_refused(self):
        a,b,c=self.sources()
        with gzip.open(c,'wb') as out:
            out.write(b'CREATE TABLE `assignments` (\n `pid` int,\n `cid` int\n);\n'
                      b'INSERT INTO `assignments` VALUES (1,10);\n')
        with self.assertRaises(ValueError):
            inspect_relationships(a,b,c)

    def test_truncated_tuple_and_decompression_bound_fail(self):
        a,b,c=self.sources()
        with gzip.open(c,'wb') as out:
            out.write(b'CREATE TABLE `assignments` (\n `cid` int,\n `pid` int\n);\n'
                      b'INSERT INTO `assignments` VALUES (1,10)')
        with self.assertRaises(ValueError):
            inspect_relationships(a,b,c)
        with self.assertRaises(ValueError):
            inspect_relationships(a,b,c,max_uncompressed_bytes=4)

    def test_strict_pair_parser_bounds(self):
        parser=AssignmentRelations({1,2},{10,20},max_pairs=1)
        with self.assertRaises(ValueError):
            parser.feed(b'(1,10),(2,20);')
        with self.assertRaises(ValueError):
            AssignmentRelations({1},{10}).feed(b"(1,'10');")

    def test_fragmented_inserts_are_supported(self):
        a,b,c=self.sources(chars=(123,),titles=(987,),pairs=((123,987),))
        with gzip.open(c,'wb') as out:
            out.write(b'CREATE TABLE `assignments` (\n `cid` int,\n `pid` int\n);\n'
                      + b'INSERT INTO `assignments` VALUES ' + b'(123,987),'*50_000 + b'(123,987);\n')
        result=inspect_relationships(a,b,c)
        self.assertEqual(result['assignment_rows'],50001)
        self.assertEqual(result['repeated_assignment_pairs'],50000)


if __name__ == '__main__':
    unittest.main()
