"""The install package must contain the executable card, not dev or local data."""

import zipfile

from scripts import build_release


def test_release_includes_card_and_frontend_tests_only_in_source(tmp_path, monkeypatch):
    monkeypatch.setattr(build_release, "OUTPUT", tmp_path)
    package = build_release.build()
    card = "custom_components/ninebot_connect/frontend/ninebot-vehicle-card.js"
    with zipfile.ZipFile(package) as archive:
        assert card in archive.namelist()
        assert archive.read(card) == (build_release.ROOT / card).read_bytes()
        assert not any(
            name.startswith(("tests/", "work/", "outputs/", "node_modules/"))
            for name in archive.namelist()
        )
    with zipfile.ZipFile(
        tmp_path / f"ninebot_connect-{build_release.VERSION}-source.zip"
    ) as archive:
        assert "tests/frontend/card.test.mjs" in archive.namelist()
        assert "package.json" in archive.namelist()
