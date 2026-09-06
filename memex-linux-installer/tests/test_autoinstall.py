import pytest
from memex_engine.autoinstall import build_autoinstall, write_autoinstall


def test_obsolete_generator_cannot_emit_unsafe_configuration(tmp_path):
    with pytest.raises(RuntimeError, match="Curtin|backend"):
        build_autoinstall(None, None)
    with pytest.raises(RuntimeError):
        write_autoinstall(tmp_path / "autoinstall.yaml", None, None)
    assert not (tmp_path / "autoinstall.yaml").exists()
