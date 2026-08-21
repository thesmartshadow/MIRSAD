from mirsad_api.connectors import (
    BlueskyConnector,
    GdeltConnector,
    GitHubConnector,
    HackerNewsConnector,
    YouTubeConnector,
)


def test_bluesky_normalization_preserves_provenance() -> None:
    item = BlueskyConnector().normalize(
        {
            "uri": "at://did:plc:abc/app.bsky.feed.post/xyz",
            "cid": "cid",
            "author": {"handle": "analyst.example", "displayName": "Analyst"},
            "record": {
                "text": "Public record text",
                "createdAt": "2026-01-01T00:00:00Z",
                "langs": ["en"],
            },
            "likeCount": 10,
            "repostCount": 2,
            "replyCount": 1,
        }
    )
    assert item.source == "bluesky"
    assert item.text == "Public record text"
    assert item.canonical_url.endswith("/analyst.example/post/xyz")
    assert item.raw_metadata["cid"] == "cid"


def test_hacker_news_and_github_normalization() -> None:
    hn = HackerNewsConnector().normalize(
        {
            "objectID": "42",
            "title": "Story",
            "author": "user",
            "points": 20,
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    github = GitHubConnector().normalize(
        {
            "id": 7,
            "full_name": "org/project",
            "html_url": "https://github.com/org/project",
            "description": "Repository description",
            "owner": {"login": "org"},
            "updated_at": "2026-01-01T00:00:00Z",
            "stargazers_count": 50,
        }
    )
    assert hn.canonical_url == "https://news.ycombinator.com/item?id=42"
    assert github.external_id == "7"
    assert github.raw_metrics["stars"] == 50


def test_gdelt_youtube_and_configuration_normalization() -> None:
    gdelt = GdeltConnector().normalize(
        {
            "url": "https://news.example/story",
            "title": "News title",
            "seendate": "20260101T120000Z",
            "domain": "news.example",
        }
    )
    youtube_connector = YouTubeConnector(api_key=None)
    youtube = youtube_connector.normalize(
        {
            "id": {"videoId": "video"},
            "snippet": {
                "title": "Video",
                "description": "Description",
                "publishedAt": "2026-01-01T00:00:00Z",
            },
            "statistics": {"viewCount": "100", "likeCount": "5"},
        }
    )
    assert gdelt.author == "news.example"
    assert youtube.raw_metrics["views"] == 100
    assert youtube_connector.validate_configuration()[0] is False
