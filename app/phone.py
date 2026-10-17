import re

from app.providers.base import InvalidPhoneNumber


def normalize_phone(raw: str) -> str:
    """Return a Cameroonian mobile number as country code + 9 digits (2376XXXXXXXX).
    Accepts 6XXXXXXXX, +237 6XX XXX XXX, 2376XXXXXXXX. Works for MTN and Orange alike.
    VERIFY on the Campay demo environment that this is the accepted format."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9 and digits.startswith("6"):
        return "237" + digits
    if len(digits) == 12 and digits.startswith("2376"):
        return digits
    raise InvalidPhoneNumber("expected a Cameroonian mobile number like 6XXXXXXXX or +2376XXXXXXXX")
