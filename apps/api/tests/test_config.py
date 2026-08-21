from pathlib import Path

from mirsad_api.config import Settings


def test_empty_optional_credentials_from_example_do_not_break_startup(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_API_ID=\nX_BEARER_TOKEN=\nYOUTUBE_API_KEY=\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.telegram_api_id is None
    assert settings.x_bearer_token is None
    assert settings.youtube_api_key is None
