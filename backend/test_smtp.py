"""Send a test PIN email using backend/.env SMTP settings.

Usage:
  python3 -m backend.test_smtp you@example.com
"""

from __future__ import annotations

import sys

from . import config, emailer


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 -m backend.test_smtp you@example.com")
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    if "@" not in email:
        print("Enter a valid email address.")
        sys.exit(1)

    if not config.smtp_configured():
        print("SMTP is not configured. Edit backend/.env and set SMTP_HOST, SMTP_USER, etc.")
        sys.exit(1)

    pin = "123456"
    print(f"SMTP host:   {config.SMTP_HOST}:{config.SMTP_PORT}")
    print(f"SMTP user:   {config.SMTP_USER}")
    print(f"TLS/SSL:     use_tls={config.SMTP_USE_TLS} use_ssl={config.SMTP_USE_SSL}")
    print(f"Sending test PIN to {email}...")
    try:
        emailer.send_pin(email, pin)
    except emailer.SmtpDeliveryError as exc:
        print(f"\nFAILED: {exc}")
        sys.exit(1)
    print("Done — check your inbox (and spam folder).")


if __name__ == "__main__":
    main()
