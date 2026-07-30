import smtplib
from email.message import EmailMessage

from . import config


class SmtpDeliveryError(RuntimeError):
    """SMTP send failed; message is safe to show in the UI."""


def _smtp_response_text(exc: smtplib.SMTPException) -> str:
    if not exc.args:
        return str(exc)
    resp = exc.args[-1]
    if isinstance(resp, bytes):
        return resp.decode("utf-8", errors="replace")
    return str(resp)


def _smtp_auth_error_message(exc: smtplib.SMTPAuthenticationError) -> str:
    detail = _smtp_response_text(exc)
    host = (config.SMTP_HOST or "").lower()
    user = config.SMTP_USER or "(SMTP_USER not set)"
    detail_lower = detail.lower()

    if "basic authentication is disabled" in detail_lower or "5.7.139" in detail:
        return (
            "SMTP login failed: Microsoft 365 has basic authentication disabled for this "
            f"mailbox ({detail.strip()}). U of T / institutional accounts often block SMTP "
            "username+password login. Ask IT to enable SMTP AUTH for your mailbox, use an "
            "account that allows SMTP (e.g. Gmail with an app password), or for local dev set "
            "FASTPHENO_DEV_PRINT_PINS=1 or keep FASTPHENO_SMTP_FALLBACK_DEV=1 (default on "
            "localhost)."
        )

    if "gmail" in host or user.endswith("@gmail.com"):
        return (
            "SMTP login failed for Gmail — use SMTP_USER=your@gmail.com and an app password "
            "(not your normal password): https://myaccount.google.com/apppasswords. "
            f"Server said: {detail.strip()}"
        )

    if any(token in host for token in ("office365", "outlook", "live.com", "microsoft")):
        return (
            "SMTP login failed for Microsoft 365 / Outlook — verify SMTP_USER and "
            "SMTP_PASSWORD, confirm SMTP AUTH is enabled for the mailbox, and use an app "
            "password if MFA is on. "
            f"Server said: {detail.strip()}"
        )

    return (
        f"SMTP login failed for {user}@{host or 'mail server'} — check SMTP_USER and "
        f"SMTP_PASSWORD. Server said: {detail.strip()}"
    )


def _smtp_error_message(exc: smtplib.SMTPException) -> str:
    detail = _smtp_response_text(exc)
    return f"SMTP error: {detail.strip()}"


def _smtp_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (OSError, TimeoutError, smtplib.SMTPServerDisconnected)):
        return True
    if isinstance(exc, smtplib.SMTPException):
        detail = _smtp_response_text(exc).lower()
        return "timed out" in detail or "connection" in detail
    return False


def _smtp_send_once(msg: EmailMessage) -> None:
    if config.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT
        ) as smtp:
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(
        config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT
    ) as smtp:
        if config.SMTP_USE_TLS:
            smtp.starttls()
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)


def _smtp_send(msg: EmailMessage) -> None:
    last_exc: BaseException | None = None
    for attempt in range(1, 4):
        try:
            _smtp_send_once(msg)
            return
        except smtplib.SMTPAuthenticationError:
            raise
        except BaseException as exc:
            last_exc = exc
            if attempt < 3 and _smtp_retryable(exc):
                continue
            raise

    if last_exc:
        raise last_exc


def send_pin(email: str, pin: str) -> None:
    if config.DEV_PRINT_PINS:
        print("\n" + "=" * 60)
        print("FastPheno sign-in PIN (dev mode)")
        print(f"  To:  {email}")
        print(f"  PIN: {pin}")
        print("=" * 60 + "\n")
        if not config.smtp_configured():
            return

    if not config.smtp_configured():
        raise SmtpDeliveryError(
            "SMTP is not configured. Copy backend/.env.example to backend/.env, "
            "set SMTP_HOST / SMTP_USER / SMTP_PASSWORD, and FASTPHENO_DEV_PRINT_PINS=0."
        )

    if config.SMTP_USER and not config.SMTP_PASSWORD:
        raise SmtpDeliveryError("SMTP_PASSWORD is missing in backend/.env")

    msg = EmailMessage()
    msg["Subject"] = "Your FastPheno sign-in code"
    msg["From"] = config.SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Your FastPheno sign-in code is:\n\n"
        f"  {pin}\n\n"
        f"Enter this 6-digit code on the login page at {config.BASE_URL}/login\n\n"
        f"This code expires in {config.PIN_MINUTES} minutes and works only once.\n"
    )

    try:
        _smtp_send(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise SmtpDeliveryError(_smtp_auth_error_message(exc)) from exc
    except smtplib.SMTPException as exc:
        raise SmtpDeliveryError(_smtp_error_message(exc)) from exc
    except OSError as exc:
        raise SmtpDeliveryError(
            f"Could not reach mail server {config.SMTP_HOST}:{config.SMTP_PORT}: {exc}"
        ) from exc
