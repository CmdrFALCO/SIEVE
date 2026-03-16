"""Tests for SIEVE content deduplication."""
from sieve.dedup import content_fingerprint, jaccard_similarity, DeduplicationStore


class TestContentFingerprint:
    def test_returns_16_char_hex(self) -> None:
        fp = content_fingerprint("This is a test of the fingerprinting system for content")
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_deterministic(self) -> None:
        text = "Same text should produce the same fingerprint every time"
        assert content_fingerprint(text) == content_fingerprint(text)

    def test_different_texts_different_fingerprints(self) -> None:
        fp1 = content_fingerprint("AI is transforming engineering workflows and tooling significantly")
        fp2 = content_fingerprint("The weather today is sunny with a chance of rain in the afternoon")
        assert fp1 != fp2


class TestJaccardSimilarity:
    def test_identical_texts(self) -> None:
        text = "This is a test of the jaccard similarity function for content"
        assert jaccard_similarity(text, text) == 1.0

    def test_completely_different(self) -> None:
        a = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
        b = "one two three four five six seven eight nine ten eleven twelve"
        sim = jaccard_similarity(a, b)
        assert sim < 0.1

    def test_similar_texts(self) -> None:
        a = ("AI is transforming engineering workflows and tooling significantly. "
             "Engineers who adopt these tools early will have a major advantage "
             "in product development speed and quality.")
        b = ("AI is transforming engineering workflows and tooling dramatically. "
             "Engineers who adopt these tools early will have a major advantage "
             "in product development speed and efficiency.")
        sim = jaccard_similarity(a, b)
        assert sim > 0.5

    def test_empty_text(self) -> None:
        assert jaccard_similarity("", "some text here") == 0.0


class TestDeduplicationStore:
    def test_register_and_exact_duplicate(self, tmp_path) -> None:
        store = DeduplicationStore(str(tmp_path / "dedup.json"))
        text = "This is a unique piece of content about AI in engineering workflows"
        store.register(text=text, url="https://example.com", title="Test Post")

        dup = store.is_duplicate(text)
        assert dup is not None
        assert dup["url"] == "https://example.com"
        assert dup["title"] == "Test Post"

    def test_no_duplicate_for_different_text(self, tmp_path) -> None:
        store = DeduplicationStore(str(tmp_path / "dedup.json"))
        store.register(
            text="AI is transforming engineering workflows and tooling significantly",
            url="https://example.com/a",
            title="Post A",
        )
        result = store.is_duplicate(
            "The weather forecast shows rain tomorrow morning in Berlin"
        )
        assert result is None

    def test_persistence_across_instances(self, tmp_path) -> None:
        path = str(tmp_path / "dedup.json")
        text = "Persistent content that should survive store reload across instances"

        store1 = DeduplicationStore(path)
        store1.register(text=text, url="https://example.com", title="Persistent")

        store2 = DeduplicationStore(path)
        dup = store2.is_duplicate(text)
        assert dup is not None
        assert dup["title"] == "Persistent"

    def test_stats(self, tmp_path) -> None:
        store = DeduplicationStore(str(tmp_path / "dedup.json"))
        assert store.stats()["total_entries"] == 0

        store.register(text="Some content for stats testing in SIEVE pipeline", url="https://example.com")
        assert store.stats()["total_entries"] == 1
