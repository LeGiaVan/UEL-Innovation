from app.models.identity import Principal
from app.repositories.users import now

GUEST_ID = "00000000-0000-4000-8000-000000000001"


def development_guest(db):
    # A separate, non-login identity keeps existing users' conversations private.
    db.ensure_guest(
        GUEST_ID, ("dbcl", "qtts", "pdt", "pns", "hc", "ctsv"), now()
    )
    return Principal(GUEST_ID, "_development_guest", False)
