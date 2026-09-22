import json
from copy import deepcopy
from pathlib import Path
import pytest
from benes_layout.config import Config
from benes_layout.network import Network
from benes_layout.cli import main
from benes_layout.banyan_workflow import candidates, generate, verify_bundle
from test_banyan_layout import config


def test_candidates_bounded_and_deterministic():
    cfg = Config.load("examples/benes/pruned-banyan/n100.json")
    choices = candidates(cfg)
    assert choices == candidates(cfg)
    assert 1 <= len(choices) <= 18
    for pitch in (34, 35):
        group = [v for v in choices if v["lane_pitch"] == pitch]
        assert len(group) <= 9
        assert any(v["exits"] == "RRRRRRR" for v in group)


def test_cli_solve_default_and_blocked(tmp_path, capsys):
    out = tmp_path / "settings.json"
    cmd = ["solve", "--topology", "pruned-banyan", "--n", "5", "--out", str(out)]
    assert main(cmd) == 0
    good = out.read_bytes()
    s = json.loads(good)
    assert (
        s["active"]
        == Network(Config(topology="pruned-banyan", active_ports=5)).reference
    )
    assert main(cmd + ["--connections", "0:0,2:1"]) == 2
    assert out.read_bytes() == good
    failure = json.loads(out.with_name("settings.json.failure.json").read_text())
    assert (
        failure["previous_output_preserved"]
        and failure["blocking"]["status"] == "blocked"
    )
    assert "previous output preserved=True" in capsys.readouterr().err
    assert main(["solve", "--n", "4", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["active"] == [[i, i] for i in range(4)]


def test_generate_dispatch_and_defaults(monkeypatch, tmp_path):
    import benes_layout.workflow as workflow

    calls = []
    monkeypatch.setattr(
        workflow,
        "generate",
        lambda cfg, out, pairs, **kw: calls.append((cfg, out, pairs))
        or {"summary": {}},
    )
    assert main(["generate", "--topology", "pruned-banyan", "--n", "5"]) == 0
    cfg, out, pairs = calls[-1]
    assert out == "output/benes/pruned-banyan/n5"
    assert pairs == Network(cfg).reference
    assert (
        main(
            [
                "generate",
                "--topology",
                "pruned-banyan",
                "--n",
                "5",
                "--connections",
                "identity",
            ]
        )
        == 0
    )
    assert calls[-1][2] == [(i, i) for i in range(5)]
    assert main(["generate", "--n", "4"]) == 0
    assert calls[-1][2] == [(i, i) for i in range(4)]


def test_bundle_repeat_and_failed_publication(tmp_path):
    cfg = config()
    net = Network(cfg)
    choice = dict(id="test", exits="RRR", pad_phase=0, lane_pitch=34)
    a = generate(cfg, tmp_path / "a", net.reference, [choice])
    b = generate(cfg, tmp_path / "b", net.reference, [choice])
    assert a["normalized_hash"] == b["normalized_hash"]
    assert a["metrics"] == b["metrics"]
    assert verify_bundle(tmp_path / "a")["electrical_nets"] == len(net.switches) + 1
    assert main(["verify", str(tmp_path / "a")]) == 0
    good = (tmp_path / "a" / "settings.json").read_bytes()
    with pytest.raises(ValueError, match="previous output preserved=True"):
        generate(cfg, tmp_path / "a", [(0, 0), (2, 1)], [choice])
    assert (tmp_path / "a" / "settings.json").read_bytes() == good
    assert verify_bundle(tmp_path / "a")["electrical_nets"] == len(net.switches) + 1
    failure = json.loads((tmp_path / "a.failure.json").read_text())
    assert failure["request"] == [[0, 0], [2, 1]]
    assert not list(tmp_path.glob(".*-pending-*"))
