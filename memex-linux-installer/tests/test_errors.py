from memex_installer.errors import ErrorCode, error_message
from memex_installer.version import PRODUCT_VERSION


def test_product_version_format():
    assert PRODUCT_VERSION.startswith("ME Linux ")


def test_bitlocker_english():
    msg = error_message(ErrorCode.BITLOCKER, "en")
    assert msg["code"] == "ME-BITLOCKER"
    assert "BitLocker" in msg["title"] or "BitLocker" in msg["body"]
    assert msg["action"]


def test_bitlocker_french():
    msg = error_message(ErrorCode.BITLOCKER, "fr")
    assert msg["code"] == "ME-BITLOCKER"
    assert msg["title"]
    assert msg["body"]


def test_all_codes_have_en_and_fr():
    for code in ErrorCode:
        for lang in ("en", "fr"):
            msg = error_message(code, lang)
            assert msg["code"].startswith("ME-")
            assert msg["title"].strip()
            assert msg["body"].strip()
            assert msg["action"].strip()
