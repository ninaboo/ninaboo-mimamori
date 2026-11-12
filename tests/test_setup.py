"""Config migration, model/runtime picking and prompt building."""
import json

from mimamori import config, llamaserver, llm, notetype, paths, tts


def test_old_config_is_migrated_once(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CONFIG_FILE", tmp_path / "config.json")
    old = {"note_type": "AnkiAutoFill JP", "done_tag": "aaf_done", "error_tag": "aaf_error",
           "volume": 0.6, "speaker_id": 5, "speaker_label": "まお – ノーマル"}
    paths.CONFIG_FILE.write_text(json.dumps(old))
    c = config.Config()
    assert (c["note_type"], c["done_tag"], c["error_tag"]) == ("Mimamori", "mimamori", "mimamori_error")
    assert c["volume"] == 0.15 and c["speaker_ids"] == [5]
    # a value chosen later survives reloads
    c["volume"] = 0.6
    c.save()
    assert config.Config()["volume"] == 0.6


def test_model_paths_are_saved_relative(cfg):
    cfg["llm_path"] = str(paths.ROOT / "models" / "llm" / "x.gguf")
    cfg.save()
    saved = json.loads(paths.CONFIG_FILE.read_text())
    assert saved["llm_path"].replace("\\", "/") == "models/llm/x.gguf"


def test_pick_llama_runtime_from_releases():
    releases = [
        {"tag_name": "v0.7.0", "assets": [{"name": "nightly-tag.txt"}]},
        {"tag_name": "b10950", "assets": [{"name": "llama-b10950-bin-win-cuda-13.3-x64.zip"},
                                          {"name": "llama-b10950-bin-win-cpu-x64.zip"},
                                          {"name": "llama-b10950-bin-win-vulkan-x64.zip"}]},
    ]
    assert llamaserver.pick_asset(releases, "cpu")[1]["name"] == "llama-b10950-bin-win-cpu-x64.zip"
    assert llamaserver.pick_asset(releases, "vulkan")[1]["name"] == "llama-b10950-bin-win-vulkan-x64.zip"
    assert llamaserver.pick_asset([], "cpu") is None


def test_pick_aivisspeech_build():
    assets = [{"name": n, "size": 1} for n in (
        "AivisSpeech-Engine-Windows-x64-CPU-1.2.0.zip",
        "AivisSpeech-Engine-Windows-x64-GPU-1.2.0.7z.001",
        "AivisSpeech-Engine-Windows-x64-GPU-1.2.0.7z.002",
        "AivisSpeech-Engine-macOS-arm64-1.2.0.7z")]
    assert [a["name"] for a in tts.choose_assets(assets, gpu=False)] == ["AivisSpeech-Engine-Windows-x64-CPU-1.2.0.zip"]
    assert len(tts.choose_assets(assets, gpu=True)) == 2


def test_plamo_prompt_format():
    p = llm.pfml3_prompt("うちに直行で", context="前の文")
    assert p == ("<|plamo:tag|>dataset<|plamo:msg|>translation"
                 "<|plamo:tag|>context<|plamo:msg|>前の文"
                 "<|plamo:tag|>input<|plamo:key|>lang<|plamo:val|>ja<|plamo:msg|>うちに直行で"
                 "<|plamo:tag|>output<|plamo:key|>lang<|plamo:val|>en<|plamo:msg|>")
    assert llm.is_plamo("models/llm/plamo-3-translate-2b-Q4_K_M.gguf")
    assert not llm.is_plamo("models/llm/qwen2.5-3b-instruct-q4_k_m.gguf")


def test_output_cleanup():
    assert llm.clean_output("Notes: casual.\nTranslation: \"Come straight to my place.\"") == \
        "Come straight to my place."
    assert llm.clean_meaning_output('Meaning: "to lose, to miss".') == "to lose, to miss"


def test_card_templates_only_use_real_fields():
    import re
    used = set(re.findall(r"\{\{[#^/]?(?:furigana:|text:)?(\w+)\}\}", notetype.FRONT + notetype.BACK))
    assert used <= set(notetype.FIELDS)


def test_dark_theme_is_default(cfg):
    assert cfg["theme"] == "dark"
