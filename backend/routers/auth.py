"""
Sign-in endpoints (public, except /me and /password).

The session lives in an HttpOnly cookie, so page scripts can never read it.
SameSite=Lax keeps other sites from sending it with their requests, and
`main.py` additionally rejects writes whose Origin isn't the app's own.
"""

import html
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from config import settings
from deps import get_session, session_token, signed_in_user
from mail.templates import layout
from models import PasswordReset, User
from schemas import (
    AcceptInviteIn,
    AuthOptionsOut,
    InviteInfoOut,
    LoginIn,
    LoginOut,
    MeOut,
    PasswordChangeIn,
    ResetPasswordIn,
    ResetRequestIn,
    TwoFactorChallengeOut,
)
from services import auth, passwords, two_factor

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Don't send a user more than one reset email in this window.
_RESET_EMAIL_INTERVAL = timedelta(minutes=2)


def client_ip(request: Request) -> str | None:
    # nginx sets X-Real-IP; direct (dev) connections use the socket address.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else None)


def _set_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        settings.session_cookie_name, raw,
        max_age=settings.session_days * 86400,
        httponly=True, secure=settings.session_cookie_secure, samesite="lax", path="/",
    )


# "Remember this device": only ever sent to the sign-in endpoints.
TRUSTED_COOKIE = "bursa_trusted"
TRUSTED_PATH = "/api/auth"


def set_trusted_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        TRUSTED_COOKIE, raw,
        max_age=settings.trusted_device_days * 86400,
        httponly=True, secure=settings.session_cookie_secure, samesite="lax",
        path=TRUSTED_PATH,
    )


async def sign_in(
    session: AsyncSession, user: User, request: Request, response: Response
) -> MeOut:
    raw = await auth.create_session(
        session, user, request.headers.get("user-agent"), client_ip(request)
    )
    _set_cookie(response, raw)
    return MeOut.model_validate(user)


def _bad_request(exc: auth.AuthError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/options", response_model=AuthOptionsOut)
async def options() -> AuthOptionsOut:
    return AuthOptionsOut(
        password_reset_by_email=mail.configured(),
        password_min_length=settings.password_min_length,
        password_min_score=settings.password_min_score,
    )


@router.post("/login", response_model=LoginOut)
async def login(
    payload: LoginIn, request: Request, response: Response,
    session: AsyncSession = Depends(get_session),
) -> LoginOut:
    """Check the password. With 2FA on (and this device not remembered) the answer
    is a challenge for /api/auth/2fa/verify instead of a session."""
    ip = client_ip(request)
    if auth.login_blocked(payload.email, ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again in a few minutes.",
        )
    user = await auth.authenticate(session, payload.email, payload.password)
    if user is None:
        auth.record_failure(payload.email, ip)
        # Same message whether the email exists or not.
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    # The only moment the plain password is known: flag it if today's policy
    # (stronger than when it was chosen, or a breach since) would refuse it.
    weak = await passwords.is_weak(payload.password, email=user.email, name=user.name)
    if weak is not None and weak != user.password_weak:
        user.password_weak = weak
        await session.commit()
    if user.has_2fa and not await two_factor.is_trusted(
        session, user, request.cookies.get(TRUSTED_COOKIE)
    ):
        # Failures aren't cleared yet: wrong codes keep counting toward the limit.
        raw, challenge = await two_factor.start_login(session, user)
        return LoginOut(two_factor=TwoFactorChallengeOut(
            token=raw,
            methods=two_factor.login_methods(user),
            email_hint=two_factor.email_hint(user.email),
            email_sent=challenge.email_sent_at is not None,
        ))
    auth.clear_failures(payload.email)
    return LoginOut(user=await sign_in(session, user, request, response))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> Response:
    raw = session_token(request)
    if raw:
        await auth.revoke_session(session, raw)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(signed_in_user)) -> MeOut:
    return MeOut.model_validate(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeIn, request: Request,
    session: AsyncSession = Depends(get_session), user: User = Depends(signed_in_user),
) -> Response:
    """Change the password; every other browser is signed out."""
    try:
        await auth.change_password(
            session, user, payload.current_password, payload.new_password, session_token(request)
        )
    except auth.AuthError as exc:
        raise _bad_request(exc) from exc
    await two_factor.notify(user, "Your Bursa password was changed",
                            "The password of your Bursa account was just changed.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- invites -----------------------------------------------------------------
@router.get("/invites/{token}", response_model=InviteInfoOut)
async def invite_info(token: str, session: AsyncSession = Depends(get_session)) -> InviteInfoOut:
    try:
        invite = await auth.open_invite(session, token)
    except auth.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return InviteInfoOut(email=invite.email or None, role=invite.role)  # type: ignore[arg-type]


@router.post("/invites/{token}/accept", response_model=MeOut, status_code=201)
async def accept_invite(
    token: str, payload: AcceptInviteIn, request: Request, response: Response,
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    """Create the account from an invite and sign it in."""
    try:
        user = await auth.accept_invite(
            session, token, payload.name, payload.password, payload.email
        )
    except auth.AuthError as exc:
        raise _bad_request(exc) from exc
    return await sign_in(session, user, request, response)


# --- password reset ----------------------------------------------------------
async def send_reset_email(user: User, link: str) -> bool:
    text = (
        f"Hi {user.name},\n\nUse this link to choose a new Bursa password. It works once "
        f"and expires in {settings.password_reset_hours} hours:\n\n{link}\n\n"
        "If you didn't ask for this, ignore this email; your password stays the same."
    )
    body = (
        f"<p>Hi {html.escape(user.name)},</p><p>Use this link to choose a new Bursa "
        f"password. It works once and expires in {settings.password_reset_hours} hours:</p>"
        f'<p><a href="{html.escape(link)}">Reset password</a></p>'
        "<p>If you didn't ask for this, ignore this email; your password stays the same.</p>"
    )
    return await mail.send_quietly(mail.Email(
        subject="Reset your Bursa password", text=text, html=layout("Reset password", body),
        to=(user.email,),
    ))


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_reset(
    payload: ResetRequestIn, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    """Email a reset link. The answer never reveals whether the email has an account."""
    done = {"detail": "If that email has an account, a reset link is on its way."}
    if not mail.configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset by email isn't available; ask your admin for a reset link.",
        )
    user = await auth.user_by_email(session, payload.email)
    if user is None or not user.is_active:
        return done
    recent = (await session.execute(
        select(PasswordReset.id).where(
            PasswordReset.user_id == user.id,
            PasswordReset.created_at > datetime.utcnow() - _RESET_EMAIL_INTERVAL,
        )
    )).first()
    if recent is None:
        raw = await auth.create_reset(session, user)
        await send_reset_email(user, auth.link(f"/reset/{raw}"))
    return done


@router.get("/password-reset/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def check_reset(token: str, session: AsyncSession = Depends(get_session)) -> Response:
    try:
        await auth.open_reset(session, token)
    except auth.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    token: str, payload: ResetPasswordIn, session: AsyncSession = Depends(get_session)
) -> Response:
    """Set a new password; signs the account out everywhere (sign in again)."""
    try:
        user = await auth.reset_password(session, token, payload.password)
    except auth.AuthError as exc:
        raise _bad_request(exc) from exc
    await two_factor.notify(user, "Your Bursa password was reset",
                            "The password of your Bursa account was reset with a reset link.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
