"""Update check and the swap script (no network or Windows needed)."""
import zipfile

from mimamori import paths, updater


def test_version_compare():
    assert updater.parse_version("v0.2.10") == (0, 2, 10)
    assert updater.is_newer("v0.2.1", "0.2.0")
    assert updater.is_newer("v0.10.0", "0.9.9")       # numeric, not alphabetical
    assert not updater.is_newer("v0.2.1", "0.2.1")
    assert not updater.is_newer("v0.2.0", "0.2.1")


def test_check_latest_picks_the_windows_zip(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"tag_name": "v0.2.1", "html_url": "https://x/releases/tag/v0.2.1", "body": "notes",
                    "assets": [{"name": "source.tar.gz", "browser_download_url": "u0", "size": 1},
                               {"name": "Mimamori-v0.2.1-windows.zip", "browser_download_url": "u1",
                                "size": 102_000_000}]}

    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: Resp())
    rel = updater.check_latest()
    assert (rel.version, rel.asset_name, rel.asset_url, rel.asset_size) == \
        ("v0.2.1", "Mimamori-v0.2.1-windows.zip", "u1", 102_000_000)


def test_download_and_stage_finds_new_app(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "TEMP", tmp_path / "temp")
    monkeypatch.setattr(paths, "DOWNLOADS", tmp_path / "temp" / "downloads")
    zpath = tmp_path / "temp" / "downloads" / "Mimamori-v0.2.1-windows.zip"
    zpath.parent.mkdir(parents=True)
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Mimamori/Mimamori.exe", "exe")
        z.writestr("Mimamori/_internal/base_library.zip", "lib")
    monkeypatch.setattr(updater, "download", lambda url, dest, **k: dest)
    rel = updater.Release("v0.2.1", "page", "", "u1", zpath.name, None)
    root = updater.download_and_stage(rel)
    assert root == tmp_path / "temp" / "update" / "Mimamori"
    assert (root / "_internal").is_dir() and not zpath.exists()


def test_swap_script_quotes_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "TEMP", tmp_path)
    monkeypatch.setattr(paths, "LOGS", tmp_path / "logs")
    (tmp_path / "update").mkdir()
    new_root = tmp_path / "update" / "Mimamori"
    app_root = tmp_path / "Nina's apps" / "Mimamori"
    script = updater.write_swap_script(new_root, app_root, pid=4242)
    text = script.read_text(encoding="utf-8-sig")
    assert "Wait-Process -Id 4242" in text
    assert "'" + str(app_root).replace("'", "''") + "'" in text     # apostrophe escaped for PowerShell
    assert script.read_bytes().startswith(b"\xef\xbb\xbf")         # BOM for Windows PowerShell
