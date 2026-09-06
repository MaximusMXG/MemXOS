from enum import Enum

from memex_installer.i18n import ERRORS


class ErrorCode(Enum):
    BITLOCKER = "ME-BITLOCKER"
    NO_WINDOWS = "ME-NO-WINDOWS"
    SPACE = "ME-SPACE"
    USB_TARGET = "ME-USB-TARGET"
    DISK_GONE = "ME-DISK-GONE"
    INSTALL_FAIL = "ME-INSTALL-FAIL"
    NO_NET = "ME-NO-NET"
    STUCK = "ME-STUCK"
    STEP_FAIL = "ME-STEP-FAIL"
    TWO_DISK = "ME-TWO-DISK"  # warning, not a hard stop


def error_message(code: ErrorCode, lang: str) -> dict[str, str]:
    lang_key = "fr" if lang.lower().startswith("fr") else "en"
    entry = ERRORS[code.value][lang_key]
    return {
        "code": code.value,
        "title": entry["title"],
        "body": entry["body"],
        "action": entry["action"],
    }
