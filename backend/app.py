"""FastPheno auth prototype — email PIN login + protected data API."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import auth_store, config, emailer
from .emailer import SmtpDeliveryError

app = FastAPI(title="FastPheno Auth Prototype", version="0.2.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

BLOCKED_STATIC_PREFIXES = ("data/fastpheno", "backend/")


def _login_context(**overrides):
    base = {
        "step": "email",
        "error": None,
        "email": "",
        "next": "/fastpheno-dashboard.html",
        "dev_mode": config.DEV_PRINT_PINS,
        "dev_pin": None,
        "smtp_fallback_warning": None,
        "pin_minutes": config.PIN_MINUTES,
    }
    base.update(overrides)
    return base


@app.on_event("startup")
def startup() -> None:
    auth_store.init_db()
    mode = config.email_delivery_mode()
    if mode == "smtp":
        print(f"FastPheno auth: emailing PINs via {config.SMTP_HOST}")
    elif mode == "dev":
        print("FastPheno auth: dev mode — PINs print to console/page (no email)")
    else:
        print(
            "FastPheno auth: WARNING — no email delivery. "
            "Set FASTPHENO_DEV_PRINT_PINS=1 or configure SMTP in backend/.env"
        )


def get_session_email(session_id: str | None = Cookie(default=None, alias=config.SESSION_COOKIE)) -> str | None:
    return auth_store.get_session_email(session_id)


def require_session(email: str | None = Depends(get_session_email)) -> str:
    if not email:
        raise HTTPException(status_code=401, detail="Not signed in")
    return email


@app.get("/api/auth/me")
def auth_me(email: str | None = Depends(get_session_email)):
    if not email:
        raise HTTPException(status_code=401, detail="Not signed in")
    return {"email": email, "authenticated": True}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/fastpheno-dashboard.html", error: str | None = None):
    err_msg = "That sign-in code is invalid or expired." if error == "invalid" else None
    return templates.TemplateResponse(
        request,
        "login.html",
        _login_context(next=next, error=err_msg),
    )


@app.post("/login", response_class=HTMLResponse)
def login_request_pin(
    request: Request,
    email: str = Form(...),
    next: str = Form("/fastpheno-dashboard.html"),
):
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        return templates.TemplateResponse(
            request,
            "login.html",
            _login_context(error="Enter a valid email address.", next=next),
        )
    if not auth_store.email_allowed(normalized):
        return templates.TemplateResponse(
            request,
            "login.html",
            _login_context(
                error="That email is not on the allow-list for this prototype.",
                next=next,
            ),
        )

    pin = auth_store.create_pin(normalized)
    smtp_fallback_warning = None
    try:
        emailer.send_pin(normalized, pin)
    except SmtpDeliveryError as exc:
        if config.SMTP_FALLBACK_DEV and not config.DEV_PRINT_PINS:
            smtp_fallback_warning = (
                f"Email could not be sent ({exc}). Showing your sign-in code here "
                "because FASTPHENO_SMTP_FALLBACK_DEV is enabled on localhost."
            )
            print(
                f"\nFastPheno SMTP fallback — PIN for {normalized}: {pin}\n"
                f"Reason: {exc}\n"
            )
        else:
            return templates.TemplateResponse(
                request,
                "login.html",
                _login_context(error=f"Could not send email: {exc}", next=next),
            )

    show_pin_on_page = config.DEV_PRINT_PINS or smtp_fallback_warning is not None
    return templates.TemplateResponse(
        request,
        "login.html",
        _login_context(
            step="pin",
            email=normalized,
            next=next,
            dev_pin=pin if show_pin_on_page else None,
            smtp_fallback_warning=smtp_fallback_warning,
        ),
    )


@app.post("/login/verify", response_class=HTMLResponse)
def login_verify_pin(
    request: Request,
    email: str = Form(...),
    pin: str = Form(...),
    next: str = Form("/fastpheno-dashboard.html"),
):
    normalized = email.strip().lower()
    if not auth_store.verify_pin(normalized, pin):
        return templates.TemplateResponse(
            request,
            "login.html",
            _login_context(
                step="pin",
                email=normalized,
                error="Invalid or expired code. Request a new one if needed.",
                next=next,
            ),
        )

    session_id = auth_store.create_session(normalized)
    response = RedirectResponse(url=next, status_code=302)
    response.set_cookie(
        key=config.SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=config.SESSION_DAYS * 86400,
    )
    return response


@app.post("/auth/logout")
def logout(session_id: str | None = Cookie(default=None, alias=config.SESSION_COOKIE)):
    auth_store.delete_session(session_id)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(config.SESSION_COOKIE)
    return response


@app.get("/api/data/fastpheno/{filepath:path}")
def protected_data(filepath: str, _email: str = Depends(require_session)):
    safe = Path(filepath).name if "/" not in filepath and "\\" not in filepath else None
    if not safe or safe != filepath:
        raise HTTPException(status_code=400, detail="Invalid path")
    target = (config.DATA_DIR / safe).resolve()
    if not str(target).startswith(str(config.DATA_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target, media_type=media_type or "application/octet-stream")


def _safe_static_path(path: str) -> Path | None:
    if not path or path.startswith("."):
        return None
    if any(path.startswith(prefix) for prefix in BLOCKED_STATIC_PREFIXES):
        return None
    target = (config.ROOT / path).resolve()
    if not str(target).startswith(str(config.ROOT.resolve())):
        return None
    if not target.is_file():
        return None
    return target


@app.get("/")
def root():
    return RedirectResponse("/fastpheno-dashboard.html", status_code=302)


@app.get("/{path:path}")
def static_files(path: str):
    if path == "fastpheno-dashboard.html":
        dashboard = config.ROOT / "fastpheno-dashboard.html"
        if dashboard.is_file():
            return FileResponse(dashboard, media_type="text/html")
    target = _safe_static_path(path)
    if not target:
        raise HTTPException(status_code=404)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target, media_type=media_type or "application/octet-stream")
