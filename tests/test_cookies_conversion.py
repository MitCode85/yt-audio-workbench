
import json
from pathlib import Path
import workbench_core as core

def test_cookie_editor_json_to_netscape(tmp_path):
    src = tmp_path/"cookies.json"
    data = {"cookies":[
        {"domain": ".example.com", "path": "/", "secure": True, "expirationDate": 0, "name": "sid", "value": "abc"},
        {"domain": "example.com", "path": "/x", "secure": False, "expires": 0, "name": "t", "value": "1"},
    ]}
    src.write_text(json.dumps(data), encoding="utf-8")
    out = core.prepare_cookies(src, cookies_browser=None, working_dir=tmp_path, log=None)
    assert out is not None
    txt = out.read_text(encoding="utf-8")
    assert "Netscape HTTP Cookie File" in txt
    assert "example.com" in txt
