"""Outgoing e-mail. The notifier depends on the Mailer protocol, so tests use an in-memory fake."""
from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from .config import settings


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, mail: Mail) -> None: ...


class ConsoleMailer:
    """Development: prints instead of sending."""
    def send(self, mail: Mail) -> None:
        print(f'--- e-mail para {mail.to}\nAssunto: {mail.subject}\n\n{mail.body}\n', flush=True)


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str):
        self.host, self.port, self.user, self.password, self.sender = host, port, user, password, sender

    def send(self, mail: Mail) -> None:
        message = EmailMessage()
        message['From'], message['To'], message['Subject'] = self.sender, mail.to, mail.subject
        message.set_content(mail.body)
        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(message)


def default_mailer() -> Mailer:
    if not settings.smtp_host:
        return ConsoleMailer()
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_password, settings.mail_from)
