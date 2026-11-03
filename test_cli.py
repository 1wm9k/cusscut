import json
from pathlib import Path

from cli import build_plan, collect_inputs, main


def test_collect_inputs_skips_output_directory(tmp_path: Path):
    source = tmp_path / "source.wav"
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "already_clean.wav").write_bytes(b"x")
    source.write_bytes(b"x")

    assert collect_inputs([tmp_path], output) == [source.resolve()]


def test_build_plan_preserves_relative_paths_and_avoids_collisions(tmp_path: Path):
    root = tmp_path / "media"
    (root / "one").mkdir(parents=True)
    (root / "two").mkdir(parents=True)
    first = root / "one" / "voice.wav"
    second = root / "two" / "voice.wav"
    first.write_bytes(b"x")
    second.write_bytes(b"x")

    plan = build_plan([root], tmp_path / "outputs", "same")
    assert [output.relative_to(tmp_path / "outputs") for _, output in plan] == [
        Path("one/voice_clean.wav"),
        Path("two/voice_clean.wav"),
    ]


def test_dry_run_json_is_machine_readable(tmp_path: Path, capsys):
    source = tmp_path / "source.wav"
    source.write_bytes(b"x")

    assert main([str(source), "--dry-run", "--json", "-o", str(tmp_path / "out")]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "planned"
    assert payload[0]["output"].endswith("source_clean.wav")


def test_existing_output_skips_model_loading(tmp_path: Path, capsys):
    source = tmp_path / "source.wav"
    output = tmp_path / "out"
    source.write_bytes(b"x")
    output.mkdir()
    (output / "source_clean.wav").write_bytes(b"x")

    assert main([str(source), "-o", str(output), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "skipped"
