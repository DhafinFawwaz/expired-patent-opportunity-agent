import json
from pathlib import Path

from jsonschema import validate

from patentic.schemas_export import export_schemas

ROOT: Path = Path(__file__).parents[2]


def test_schemas_export_and_validate_fixtures(tmp_path: Path) -> None:
    written: list[Path] = export_schemas(tmp_path)
    names: set[str] = {p.name for p in written}
    assert {"fixture-case.schema.json", "evidence-record.schema.json"} <= names
    assert "research-request.schema.json" in names
    schema: dict[str, object] = json.loads((tmp_path / "fixture-case.schema.json").read_text())
    for path in sorted((ROOT / "fixtures" / "synthetic").glob("*.json")):
        validate(json.loads(path.read_text()), schema)


def test_committed_schemas_are_current(tmp_path: Path) -> None:
    for path in export_schemas(tmp_path):
        committed: Path = ROOT / "schemas" / path.name
        assert committed.read_text() == path.read_text(), (
            f"run `patentic schemas export`: {path.name}"
        )
