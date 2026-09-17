import json

from waksman_layout.cli import main


def test_failed_generation_has_no_success_artifact(tmp_path):
    config = tmp_path / "bad.json"
    config.write_text(json.dumps({"n": 16, "max_swap_columns": 1}))
    out = tmp_path / "out"
    assert main(["generate", "--config", str(config), "--out", str(out)]) == 2
    report = json.loads((out / "report.json").read_text())
    assert report["success"] is False
    assert all(c["status"] == "failed" for c in report["candidates"])
    assert not (out / "layout.gds").exists()


def test_solve_json_roundtrip(tmp_path):
    out = tmp_path / "states.json"
    assert (
        main(["solve", "--n", "100", "--connections", "0:73,1:4", "--out", str(out)])
        == 0
    )
    from waksman_layout.network import Network

    s = json.loads(out.read_text())
    Network(100).verify(s)
    assert s["active"] == [[0, 73], [1, 4]]
