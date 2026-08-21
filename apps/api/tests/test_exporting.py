from mirsad_api.services.exporting import export_csv


def test_csv_is_utf8_with_bom_and_prevents_spreadsheet_formulas() -> None:
    payload = {
        "records": [
            {
                "query": "العراق",
                "source": "fixture",
                "source_type": "post",
                "author": '=HYPERLINK("https://invalid.example")',
                "title": "+formula",
                "text": "نص عربي",
                "publication_time": None,
                "fetch_time": "2026-08-08T00:00:00Z",
                "original_url": "https://example.invalid/1",
                "final_score": 75,
                "relevance": 90,
                "freshness": 80,
                "engagement": 20,
                "source_confidence": 60,
                "cross_source_presence": 0,
                "duplicate_group": None,
                "cluster": None,
            }
        ]
    }

    decoded = export_csv(payload).decode("utf-8-sig")
    assert "العراق" in decoded
    assert "'=HYPERLINK" in decoded
    assert "'+formula" in decoded
