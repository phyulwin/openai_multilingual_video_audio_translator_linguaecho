# test_config.py — Verify explicit local credentials override launcher defaults.
import os
import subprocess
import sys
from pathlib import Path
import pytest
from run import create_listener


def test_duplicate_server_cannot_share_port():
    """Reject a second listener instead of routing some requests to stale credentials."""
    with create_listener(0) as first:
        with pytest.raises(OSError):
            create_listener(first.getsockname()[1])


def test_local_env_overrides_inherited_key(tmp_path):
    """Load a copied configuration module without reading or exposing real secrets."""
    module = tmp_path / 'backend' / 'app' / 'config.py'
    module.parent.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / 'app' / 'config.py'
    module.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
    (tmp_path / '.env').write_text('OPENAI_API_KEY=local-test-value\n', encoding='utf-8')
    (tmp_path / '.env.example').write_text('OPENAI_API_KEY=template-test-value\n', encoding='utf-8')
    environment = dict(os.environ, OPENAI_API_KEY='inherited-test-value')
    script = (
        'import runpy, sys; '
        'config = runpy.run_path(sys.argv[1]); '
        'assert config["os"].environ["OPENAI_API_KEY"] == "local-test-value"'
    )
    result = subprocess.run([sys.executable, '-c', script, str(module)],
                            env=environment, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode()
