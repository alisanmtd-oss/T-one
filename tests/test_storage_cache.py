import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from ai_ecommerce_director.storage import (
    append_record,
    read_records,
    record_path,
    write_records,
)
from ai_ecommerce_director.types import IntakeRecord


class StorageCacheTest(TestCase):
    def test_append_is_visible_to_subsequent_read(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            append_record(root, IntakeRecord(record_type="hot_link", fields={"url": "https://a.example.com"}, raw_text="a"))
            # Warm the cache, then append again; the new record must be visible.
            self.assertEqual(len(read_records(root, "hot_link")), 1)
            append_record(root, IntakeRecord(record_type="hot_link", fields={"url": "https://b.example.com"}, raw_text="b"))
            urls = {record.fields["url"] for record in read_records(root, "hot_link")}
            self.assertEqual(urls, {"https://a.example.com", "https://b.example.com"})

    def test_duplicate_key_merges_instead_of_appending(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            append_record(root, IntakeRecord(record_type="hot_link", fields={"url": "https://dup.example.com"}, raw_text="first"))
            read_records(root, "hot_link")  # warm cache + dedupe index
            append_record(
                root,
                IntakeRecord(record_type="hot_link", fields={"url": "https://dup.example.com", "note": "second"}, raw_text="second"),
            )
            records = read_records(root, "hot_link")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].fields["note"], "second")
            self.assertEqual(int(records[0].metadata.get("dedupe_count")), 2)

    def test_external_file_change_invalidates_cache(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            append_record(root, IntakeRecord(record_type="hot_link", fields={"url": "https://x.example.com"}, raw_text="x"))
            self.assertEqual(len(read_records(root, "hot_link")), 1)
            # Rewrite the file out-of-band with two records.
            path = record_path(root, "hot_link")
            extra = [
                IntakeRecord(record_type="hot_link", fields={"url": "https://x.example.com"}, raw_text="x").to_dict(),
                IntakeRecord(record_type="hot_link", fields={"url": "https://y.example.com"}, raw_text="y").to_dict(),
            ]
            path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in extra) + "\n", encoding="utf-8")
            urls = {record.fields["url"] for record in read_records(root, "hot_link")}
            self.assertEqual(urls, {"https://x.example.com", "https://y.example.com"})

    def test_mutating_returned_record_does_not_corrupt_cache(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            append_record(root, IntakeRecord(record_type="hot_link", fields={"url": "https://m.example.com"}, raw_text="m"))
            first = read_records(root, "hot_link")[0]
            first.fields["url"] = "https://mutated.example.com"
            first.metadata["touched"] = True
            # A fresh read must reflect the persisted value, not the in-place mutation.
            second = read_records(root, "hot_link")[0]
            self.assertEqual(second.fields["url"], "https://m.example.com")
            self.assertNotIn("touched", second.metadata)

    def test_write_records_is_atomic_and_leaves_no_temp_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records = [
                IntakeRecord(record_type="hot_link", fields={"url": "https://1.example.com"}, raw_text="1"),
                IntakeRecord(record_type="hot_link", fields={"url": "https://2.example.com"}, raw_text="2"),
            ]
            write_records(root, "hot_link", records)
            self.assertEqual(len(read_records(root, "hot_link")), 2)
            leftover = list((root / "data" / "real_world").glob("*.tmp"))
            self.assertEqual(leftover, [])
