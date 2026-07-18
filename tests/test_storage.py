import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from ai_ecommerce_director.storage import read_records, record_path
from ai_ecommerce_director.types import IntakeRecord


class StorageTest(TestCase):
    def test_read_records_skips_bom_only_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = record_path(root, "hot_link")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\ufeff", encoding="utf-8")

            self.assertEqual(read_records(root), [])

    def test_read_records_skips_invalid_lines(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            record = IntakeRecord(record_type="hot_link", fields={"url": "https://example.com"}, raw_text="test")
            path = record_path(root, "hot_link")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\ufeff\nnot-json\n" + json.dumps(record.to_dict(), ensure_ascii=False) + "\n", encoding="utf-8")

            records = read_records(root)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].fields["url"], "https://example.com")
