"""
Two-factor authentication endpoints.

* Sign-in second step (public, identified by the challenge token from
  /api/auth/login): verify a code, or email a new one.
* Managing your own methods (signed in). Turning a method off and new recovery
  codes need the password again, so an unattended signed-in browser can't
  weaken the account.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from accounts import auth, two_factor
from accounts.models import User
from accounts.routes.auth import (
    TRUSTED_COOKIE,
    TRUSTED_PATH,
    client_ip,
    set_trusted_cookie,
    sign_in,
)
from accounts.schemas import (
    CodeIn,
    MeOut,
    PasswordConfirmIn,
    RecoveryCodesOut,
    TotpSetupOut,
    TwoFactorStatusOut,
    TwoFactorTokenIn,
    TwoFactorVerifyIn,
)
from deps import get_session, signed_in_user

router = APIRouter(prefix="/api/auth/2fa", tags=["auth"])


def _bad(exc: auth.AuthError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --- sign-in second step (public) ------------------------------------------------
@router.post("/verify", response_model=MeOut)
async def verify(
    payload: TwoFactorVerifyIn, request: Request, response: Response,
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    ip = client_ip(request)
    try:
        user = await two_factor.challenge_user(session, payload.token)
    except auth.AuthError as exc:
        raise _bad(exc) from exc
    if await auth.login_blocked(user.email, ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in a few minutes.",
        )
    try:
        await two_factor.verify_login(session, payload.token, payload.method, payload.code)
    except auth.AuthError as exc:
        await auth.record_failure(user.email, ip)
        raise _bad(exc) from exc
    await auth.clear_failures(user.email)
    if payload.remember_device:
        set_trusted_cookie(
            response,
            await two_factor.trust_device(session, user, request.headers.get("user-agent")),
        )
    return await sign_in(session, user, request, response)


@router.post("/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend(
    payload: TwoFactorTokenIn, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    """Email a new sign-in code (at most one a minute)."""
    try:
        await two_factor.resend_login_email(session, payload.token)
    except auth.AuthError as exc:
        raise _bad(exc) from exc
    return {"detail": "Code sent"}


# --- managing your methods ----------------------------------------------------------
@router.get("", response_model=TwoFactorStatusOut)
async def get_status(
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user)
) -> TwoFactorStatusOut:
    return TwoFactorStatusOut(
        totp=user.totp_secret is not None,
        email=user.mfa_email,
        email_available=mail.configured(),
        recovery_codes_left=await two_factor.recovery_codes_left(session, user.id),
        trusted_devices=await two_factor.trusted_device_count(session, user.id),
        required=user.role == "admin",
    )


@router.post("/totp", response_model=TotpSetupOut)
async def totp_setup(
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user)
) -> TotpSetupOut:
    """A new secret to add to an authenticator app (not active until confirmed)."""
    secret = await two_factor.begin_totp(session, user)
    uri = two_factor.otpauth_uri(secret, user.email)
    return TotpSetupOut(secret=secret, uri=uri, qr_svg=two_factor.qr_svg(uri))


@router.post("/totp/confirm", response_model=RecoveryCodesOut)
async def totp_confirm(
    payload: CodeIn,
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user),
) -> RecoveryCodesOut:
    """Turn the app on with a code from it. Returns recovery codes when 2FA was off."""
    try:
        return RecoveryCodesOut(
            recovery_codes=await two_factor.confirm_totp(session, user, payload.code)
        )
    except auth.AuthError as exc:
        raise _bad(exc) from exc


@router.post("/email", status_code=status.HTTP_202_ACCEPTED)
async def email_setup(
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user)
) -> dict[str, str]:
    """Email a code to the account address; confirming it turns email codes on."""
    try:
        await two_factor.begin_email(session, user)
    except auth.AuthError as exc:
        raise _bad(exc) from exc
    return {"detail": f"Code sent to {user.email}"}


@router.post("/email/confirm", response_model=RecoveryCodesOut)
async def email_confirm(
    payload: CodeIn,
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user),
) -> RecoveryCodesOut:
    try:
        return RecoveryCodesOut(
            recovery_codes=await two_factor.confirm_email(session, user, payload.code)
        )
    except auth.AuthError as exc:
        raise _bad(exc) from exc


@router.post("/{method}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable(
    method: Literal["totp", "email"], payload: PasswordConfirmIn,
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user),
) -> Response:
    try:
        await two_factor.disable_method(session, user, method, payload.password)
    except auth.AuthError as exc:
        raise _bad(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/recovery-codes", response_model=RecoveryCodesOut)
async def new_recovery_codes(
    payload: PasswordConfirmIn,
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user),
) -> RecoveryCodesOut:
    """Replace the recovery codes (the old ones stop working)."""
    try:
        return RecoveryCodesOut(
            recovery_codes=await two_factor.regenerate_codes(session, user, payload.password)
        )
    except auth.AuthError as exc:
        raise _bad(exc) from exc


@router.delete("/trusted-devices", status_code=status.HTTP_204_NO_CONTENT)
async def forget_trusted_devices(
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user)
) -> Response:
    """Every remembered device (this one too) asks for a code at the next sign-in."""
    await two_factor.forget_devices(session, user.id)
    await session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(TRUSTED_COOKIE, path=TRUSTED_PATH)
    return response
