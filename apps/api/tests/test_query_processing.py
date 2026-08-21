from mirsad_api.domains.query import (
    classify_query,
    detect_language,
    normalize_arabic,
    normalize_text,
    process_query,
)


def test_query_normalization_preserves_original_and_normalizes_tokens() -> None:
    processed = process_query("  Public   POLICY  ")
    assert processed.original == "Public   POLICY"
    assert processed.normalized == "public policy"
    assert processed.tokens == ("public", "policy")
    assert processed.language == "en"


def test_arabic_normalization_removes_diacritics_and_unifies_letters() -> None:
    assert normalize_arabic("إِعْلَامٌ عَرَبِيّ") == "اعلام عربي"
    assert normalize_text("  الآخِرَة  ") == "الاخره"
    processed = process_query("الأخبار العراقية")
    assert processed.language == "ar"
    assert "اخبار عراقيه" in processed.variants


def test_language_detection_is_deterministic() -> None:
    assert detect_language("سياسة عامة") == "ar"
    assert detect_language("public policy") == "en"
    assert detect_language("123") == "und"


def test_query_intent_and_unicode_controls_are_handled_conservatively() -> None:
    assert process_query('"open data"').exact_phrase is True
    assert process_query("#بغداد").intent == "hashtag"
    assert process_query("@analyst").intent == "handle"
    assert process_query("MIRSAD العراق").intent == "mixed_language"
    assert process_query("public\u200b policy").normalized == "public policy"
    assert process_query("العراق ٢٠٢٦").normalized == "العراق 2026"


def test_arabic_normalization_does_not_merge_unrelated_letters() -> None:
    assert normalize_text("سالم") != normalize_text("صالم")
    assert normalize_text("قانون") != normalize_text("كانون")


def test_query_type_classification_is_deterministic_and_intent_preserving() -> None:
    assert classify_query(process_query('"open data"')) == "EXACT_PHRASE"
    assert classify_query(process_query("#بغداد")) == "HASHTAG"
    assert classify_query(process_query("@mirsad")) == "HANDLE"
    assert classify_query(process_query("example.org/report")) == "URL"
    assert classify_query(process_query("MIRSAD العراق")) == "MIXED_LANGUAGE"
    assert classify_query(process_query("National Cyber Center")) == "RARE_ENTITY"
    assert classify_query(process_query("climate adaptation policy")) == "MULTI_TERM_TOPIC"
    assert classify_query(process_query("climate")) == "SHORT_AMBIGUOUS"
