import smtplib
from dataclasses import dataclass


@dataclass
class SmtpConnectionConfig:
    """Everything needed to open and authenticate an SMTP connection —
    shared between the superadmin "Verify" endpoint and actually sending
    mail (see app/core/email.py), so both use the exact same connection
    logic.
    """

    server: str
    port: int
    username: str
    password: str
    timeout: int
    security: str = ""  # "", "tls", or "ssl" (case-insensitive)
    reply_to: str = ""


def open_connection(config: SmtpConnectionConfig) -> smtplib.SMTP:
    """Opens and authenticates a connection per `config`. Raises on any
    connection/auth failure. Callers are responsible for `.quit()`-ing the
    returned connection once done.
    """
    security = config.security.strip().lower()
    if security == "ssl":
        server = smtplib.SMTP_SSL(config.server, config.port, timeout=config.timeout)
    else:
        server = smtplib.SMTP(config.server, config.port, timeout=config.timeout)

    server.ehlo()
    if security not in ("ssl", "none"):
        server.starttls()
        server.ehlo()
    server.login(config.username, config.password)
    return server
