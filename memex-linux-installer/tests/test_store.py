import json

import pytest

from memex_installer.store import DEFAULT_TIMEZONE, Store, load_store


def test_missing_file_defaults(tmp_path):
    assert load_store(tmp_path / 'none.json') == Store(DEFAULT_TIMEZONE, '')


def test_valid_store(tmp_path):
    p = tmp_path / 's.json'
    p.write_text(json.dumps({'timezone': 'America/Regina', 'name': 'Regina'}))
    assert load_store(p) == Store('America/Regina', 'Regina')


@pytest.mark.parametrize('content', ['{"timezone": "../etc/passwd"}', '{"timezone": "Edmonton"}',
                                     '{"timezone": 5}', 'not json', '{"timezone": "America/Edmonton", "name": 3}'])
def test_invalid_store_raises(tmp_path, content):
    p = tmp_path / 's.json'
    p.write_text(content)
    with pytest.raises(ValueError):
        load_store(p)
