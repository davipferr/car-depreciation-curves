import polars as pl

from pipeline import frames


def test_memo_rebuilds_when_code_version_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(frames, "FRAMES", tmp_path)
    calls = []

    def build():
        calls.append(1)
        return pl.DataFrame({"x": [len(calls)]})

    monkeypatch.setattr(frames, "CODE_VERSION", "aaaaaaaaaaaa")
    assert frames.memo("t", build)["x"].to_list() == [1]
    assert frames.memo("t", build)["x"].to_list() == [1]  # fresh cache hit
    assert len(calls) == 1

    # Same age, different pipeline code: must rebuild and drop the stale copy.
    monkeypatch.setattr(frames, "CODE_VERSION", "bbbbbbbbbbbb")
    assert frames.memo("t", build)["x"].to_list() == [2]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["t-bbbbbbbbbbbb.parquet"]


def test_memo_drops_the_old_unversioned_name(tmp_path, monkeypatch):
    monkeypatch.setattr(frames, "FRAMES", tmp_path)
    monkeypatch.setattr(frames, "CODE_VERSION", "aaaaaaaaaaaa")
    pl.DataFrame({"x": [0]}).write_parquet(tmp_path / "precos-2014-4.parquet")
    frames.memo("precos-2014-4", lambda: pl.DataFrame({"x": [1]}))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["precos-2014-4-aaaaaaaaaaaa.parquet"]


def test_memo_cleanup_keeps_other_samples(tmp_path, monkeypatch):
    # A partial build (CDC_FAMILIAS) tags its frames with a hash of the family list;
    # rebuilding the full sample must not delete them, and vice versa.
    monkeypatch.setattr(frames, "FRAMES", tmp_path)
    monkeypatch.setattr(frames, "CODE_VERSION", "aaaaaaaaaaaa")
    frames.memo("catalogo-2014-4-1a2b3c4d", lambda: pl.DataFrame({"x": [1]}))
    frames.memo("catalogo-2014-4", lambda: pl.DataFrame({"x": [1]}))
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "catalogo-2014-4-1a2b3c4d-aaaaaaaaaaaa.parquet",
        "catalogo-2014-4-aaaaaaaaaaaa.parquet",
    ]


def test_code_version_is_stable():
    assert frames._code_version() == frames.CODE_VERSION
    assert len(frames.CODE_VERSION) == 12
