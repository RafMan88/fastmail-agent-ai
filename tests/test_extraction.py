from src.interviews_extraction import extract_with_claude

def test_extract_with_claude(monkeypatch):
    class FakeMessages:
        def create(self, *args, **kwargs):
            class FakeResponse:
                content = [{"text": '{"is_interview": true, "esn": "TestESN", "client": "TestClient", "date": "2026-04-16", "poste": "QA Lead", "source": ["subject"]}'}]
            return FakeResponse()

    class FakeAnthropic:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    # Patch Anthropic class used in interviews_extraction.py
    monkeypatch.setattr("src.extraction.Anthropic", FakeAnthropic)

    result = extract_with_claude("Subject: Entretien", "fake_key")

    assert result["is_interview"] is True
    assert result["client"] == "TestClient"
