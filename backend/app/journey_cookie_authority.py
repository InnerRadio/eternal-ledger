from datetime import datetime

from fastapi import Request, Response


JOURNEY_COOKIE_NAME = "pp_journey"
JOURNEY_COOKIE_PATH = "/"
JOURNEY_COOKIE_HTTPONLY = True
JOURNEY_COOKIE_SECURE = True
JOURNEY_COOKIE_SAMESITE = "lax"


def read_journey_cookie(
    request: Request,
) -> str | None:
    """
    Read browser-carried journey continuity material.

    This is transport retrieval only.

    Presence does not establish:
    - valid journey continuity
    - authentication
    - membership
    - Campaign Participation
    - reward authority
    - settlement authority
    """

    return request.cookies.get(
        JOURNEY_COOKIE_NAME
    )


def set_journey_cookie(
    response: Response,
    journey_reference: str,
    *,
    max_age: int | None = None,
    expires: datetime | str | int | None = None,
) -> None:
    """
    Carry already-authorized journey material to the browser.

    This helper does not:
    - generate the journey reference
    - validate canonical reference grammar
    - resolve Attribution Context
    - create Attribution Context
    - rotate journey authority
    - bind participant identity
    - authenticate a user
    """

    if not isinstance(
        journey_reference,
        str,
    ):
        raise TypeError(
            "journey_reference must be a string."
        )

    response.set_cookie(
        key=JOURNEY_COOKIE_NAME,
        value=journey_reference,
        max_age=max_age,
        expires=expires,
        path=JOURNEY_COOKIE_PATH,
        secure=JOURNEY_COOKIE_SECURE,
        httponly=JOURNEY_COOKIE_HTTPONLY,
        samesite=JOURNEY_COOKIE_SAMESITE,
    )


def clear_journey_cookie(
    response: Response,
) -> None:
    """
    Remove browser transport only.

    Clearing pp_journey does not delete or mutate canonical
    Attribution Context provenance.

    The expired Set-Cookie uses the same locked security scope as
    normal journey-cookie transport.
    """

    response.set_cookie(
        key=JOURNEY_COOKIE_NAME,
        value="",
        max_age=0,
        expires=0,
        path=JOURNEY_COOKIE_PATH,
        secure=JOURNEY_COOKIE_SECURE,
        httponly=JOURNEY_COOKIE_HTTPONLY,
        samesite=JOURNEY_COOKIE_SAMESITE,
    )
