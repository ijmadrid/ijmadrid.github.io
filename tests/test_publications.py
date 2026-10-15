"""Regression checks for synchronisation and the preservation of local additions."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publications", ROOT / "scripts/publications.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)


class BibliographyTests(unittest.TestCase):
    def test_published_version_replaces_preprint_metadata_but_keeps_attachments_and_url(self):
        preprint = {"id": "my-paper", "url": "/publications/my-paper/", "title": "A preprint", "kind": "preprint", "date": "2022", "arxiv": "2212.03163", "links": {"manuscript": "/files/author.pdf", "slides": "/files/slides.pdf"}, "aliases": ["doi:10.1000/paper"]}
        article = {"id": "imported-id", "title": "A published paper", "kind": "article", "date": "2023-08", "doi": "10.1000/paper", "links": {"article": "https://doi.org/10.1000/paper"}}
        merged = pub.merge_record(preprint, article)
        self.assertEqual(merged["id"], "my-paper")
        self.assertEqual(merged["url"], "/publications/my-paper/")
        self.assertEqual(merged["title"], "A published paper")
        self.assertEqual(merged["date"], "2023-08")
        self.assertEqual(merged["links"]["slides"], "/files/slides.pdf")
        self.assertIn("arxiv:2212.03163", pub.aliases(merged))

    def test_preprint_cannot_downgrade_journal_entry(self):
        article = {"id": "paper", "title": "Published title", "kind": "article", "date": "2023", "doi": "10.1000/paper"}
        early = {"id": "early", "title": "Earlier title", "kind": "preprint", "date": "2022", "arxiv": "2212.03163", "links": {"preprint": "https://arxiv.org/abs/2212.03163"}}
        merged = pub.merge_record(article, early)
        self.assertEqual(merged["title"], "Published title")
        self.assertEqual(merged["kind"], "article")
        self.assertIn("preprint", merged["links"])

    def test_local_null_removes_a_resource_and_aliases_match_normalised_doi(self):
        record = {"id": "p", "doi": "10.1000/example", "links": {"article": "https://doi.org/10.1000/example", "slides": "/files/old.pdf"}}
        result = pub.apply_overrides(record, {"https://doi.org/10.1000/EXAMPLE": {"links": {"slides": None, "code": "https://example.org/code"}}})
        self.assertIsNone(result["links"]["slides"])
        self.assertIn("code", result["links"])
        self.assertEqual(record["links"]["slides"], "/files/old.pdf")

    def test_network_failure_and_empty_response_do_not_replace_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_data").mkdir()
            (root / "_config.yml").write_text("publication_sync:\n  orcid: 0000-0001-7484-2073\n")
            cache = root / "_data/publications_imported.json"
            original = b'{"records":[{"id":"saved","title":"Keep me"}]}\n'
            cache.write_bytes(original)
            with patch.object(pub, "get_json", side_effect=URLError("offline")):
                self.assertFalse(pub.sync(root))
            self.assertEqual(cache.read_bytes(), original)
            with patch.object(pub, "get_json", return_value={"group": []}):
                self.assertFalse(pub.sync(root))
            self.assertEqual(cache.read_bytes(), original)

    def test_explicit_alias_bridges_two_source_records_without_title_matching(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_data").mkdir()
            (root / "_publications").mkdir()
            (root / "_data/publications_manual.yml").write_text("- id: keep-my-id\n  title: Early title\n  date: '2022'\n  kind: preprint\n  arxiv: '2212.03163'\n  aliases: ['doi:10.1000/published']\n  links:\n    slides: /files/talk.pdf\n")
            cache = {"records": [{"id": "doi-record", "title": "Published title", "kind": "article", "date": "2023", "doi": "10.1000/published"}, {"id": "arxiv-record", "title": "Early title", "kind": "preprint", "date": "2022", "arxiv": "2212.03163"}]}
            (root / "_data/publications_imported.json").write_text(json.dumps(cache))
            records = pub.build(root)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["id"], "keep-my-id")
            self.assertEqual(records[0]["title"], "Published title")
            self.assertEqual(records[0]["links"]["slides"], "/files/talk.pdf")
            self.assertTrue((root / "_generated/publications/keep-my-id.md").exists())

    def test_same_title_different_identifiers_are_not_silently_merged(self):
        first = {"id": "a", "title": "Same title", "doi": "10.1000/a"}
        second = {"id": "b", "title": "Same title", "doi": "10.1000/b"}
        self.assertFalse(pub.aliases(first) & pub.aliases(second))

    def test_dates_and_url_validation(self):
        self.assertEqual(pub.normalise_date("2025/7/19"), "2025-07-19")
        self.assertEqual(pub.normalise_date("2024"), "2024")
        with self.assertRaises(ValueError):
            pub.normalise_date("2025-02-30")
        for unsafe in ["javascript:alert(1)", "//external.example/file.pdf", "data:text/html,test"]:
            with self.assertRaises(ValueError):
                pub.allowed_url(unsafe)

    def test_source_external_doi_url_does_not_override_the_identifier(self):
        work = {"put-code": 1, "title": {"title": {"value": "Test"}}, "type": "journal-article", "external-ids": {"external-id": [{"external-id-type": "doi", "external-id-value": "10.1000/correct", "external-id-url": {"value": "https://wrong.example/file.pdf"}, "external-id-relationship": "self"}]}}
        record = pub.orcid_record(work)
        self.assertEqual(record["links"]["article"], "https://doi.org/10.1000/correct")

    def test_curated_doi_keeps_cached_authors_when_crossref_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_data").mkdir()
            (root / "_publications").mkdir()
            (root / "_config.yml").write_text("publication_sync:\n  orcid: 0000-0001-7484-2073\n")
            (root / "_publications/local.md").write_text("---\npublication_id: local\ntitle: Local paper\ndate: '2024'\nlink: https://doi.org/10.1000/local\n---\n")
            cache = {"records": [{"id": "local", "doi": "10.1000/local", "kind": "article", "authors": [{"name": "Alice Example"}], "source": ["crossref"]}]}
            (root / "_data/publications_imported.json").write_text(json.dumps(cache))
            work = {"put-code": 7, "title": {"title": {"value": "Another work"}}, "type": "working-paper"}
            def response(url, **kwargs):
                if url.endswith('/works'):
                    return {"group": [{"work-summary": [work]}]}
                if '/work/7' in url:
                    return work
                raise URLError("Crossref unavailable")
            with patch.object(pub, "get_json", side_effect=response), patch.object(pub.time, "sleep"):
                self.assertTrue(pub.sync(root))
            imported = json.loads((root / "_data/publications_imported.json").read_text())['records']
            local = next(x for x in imported if x['id'] == 'local')
            self.assertEqual(local['authors'][0]['name'], 'Alice Example')

    def test_bibtex_preserves_compound_surnames(self):
        record = {"id": "p", "kind": "article", "title": "Example", "authors": [{"name": "Meriem El Karoui", "given": "Meriem", "family": "El Karoui"}], "year": 2026}
        self.assertIn('El Karoui, Meriem', pub.bibtex(record))

    def test_title_destination_prefers_the_journal_for_articles_and_arxiv_for_preprints(self):
        links = {"article": "https://doi.org/10.1000/example", "preprint": "https://arxiv.org/abs/2609.30970", "hal": "https://hal.science/hal-example", "manuscript": "/files/author.pdf"}
        record = {"url": "/publications/legacy/", "kind": "article", "links": links}
        self.assertEqual(pub.primary_url(record), links["article"])
        record["kind"] = "preprint"
        self.assertEqual(pub.primary_url(record), links["preprint"])
        del links["preprint"]
        self.assertEqual(pub.primary_url(record), links["hal"])

    def test_title_destination_uses_an_available_manuscript_or_thesis(self):
        record = {"url": "/publications/legacy/", "kind": "article", "links": {"manuscript": "/files/author.pdf"}}
        self.assertEqual(pub.primary_url(record), "/files/author.pdf")
        record.update(kind="thesis", links={"thesis": "/files/thesis.pdf", "hal": "https://hal.science/hal-example"})
        self.assertEqual(pub.primary_url(record), "/files/thesis.pdf")
        record["links"] = {}
        self.assertEqual(pub.primary_url(record), record["url"])


if __name__ == "__main__":
    unittest.main()
