"""Email setup check: status and a test message (no feature sends email yet)."""

from fastapi import APIRouter, HTTPException

import mail
from mail.schemas import MailStatusOut, MailTestOut
from mail.templates import layout

router = APIRouter(prefix="/api/mail", tags=["mail"])


@router.get("/status", response_model=MailStatusOut)
async def mail_status() -> MailStatusOut:
    return MailStatusOut.model_validate(mail.status())


@router.post("/test", response_model=MailTestOut)
async def mail_test() -> MailTestOut:
    """Send a test email to the default recipients (MAIL_TO)."""
    if mail.configured() and not mail.status()["recipients"]:
        raise HTTPException(status_code=400, detail="Set MAIL_TO in backend/.env to receive it.")
    text = "Email from Bursa is working. Future notifications will arrive here."
    try:
        message_id = await mail.send(
            mail.Email(
                subject="Bursa test email",
                text=text,
                html=layout("Email is working", f"<p>{text}</p>"),
            )
        )
    except mail.MailNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except mail.MailBusyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except mail.MailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MailTestOut(delivered=True, message_id=message_id)
