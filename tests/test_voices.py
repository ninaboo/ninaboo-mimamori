"""Voice manager: reading what the user pastes, and the engine's model list."""
import pytest

from mimamori import tts

UUID = "47e53151-a378-46f3-abee-ce13aa07feb1"
DOWNLOAD = f"https://api.aivis-project.com/v1/aivm-models/{UUID}/download?model_type=AIVMX"


def test_aivishub_page_link():
    assert tts.model_source_url(f"https://hub.aivis-project.com/aivm-models/{UUID}") == DOWNLOAD


def test_bare_model_id():
    assert tts.model_source_url(f"  {UUID.upper()}  ") == DOWNLOAD


def test_direct_aivmx_link_is_kept():
    url = "https://example.com/voices/mine.aivmx"
    assert tts.model_source_url(url) == url


def test_rubbish_is_rejected():
    with pytest.raises(ValueError):
        tts.model_source_url("my favourite voice")


def test_models_are_parsed_and_sorted():
    class Resp:
        status_code = 200

        def json(self):
            return {
                "u2": {"manifest": {"name": "zonoko", "version": "1.1.0", "creators": ["A", "B"],
                                    "speakers": [{"name": "zonoko", "styles": [{}, {}, {}]}]},
                       "is_loaded": True, "is_update_available": True, "latest_version": "1.2.0",
                       "is_default_model": False, "is_private_model": False, "file_size": 250_000_000},
                "u1": {"manifest": {"name": "Anneli", "version": "1.0.0",
                                    "speakers": [{"name": "Anneli", "styles": [{}] * 6}]},
                       "is_default_model": True, "file_size": 260_000_000},
            }

    class Http:
        def get(self, url, timeout):
            assert url.endswith("/aivm_models")
            return Resp()

    eng = tts.Engine(lambda: "http://127.0.0.1:10111")
    eng.http = Http()
    a, z = eng.models()
    assert (a.name, a.styles, a.default, round(a.size_mb)) == ("Anneli", 6, True, 260)
    assert (z.name, z.styles, z.update_available, z.latest_version, z.creators) == \
        ("zonoko", 3, True, "1.2.0", "A, B")
