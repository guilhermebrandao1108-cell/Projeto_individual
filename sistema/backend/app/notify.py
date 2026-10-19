"""Deadline e-mails: `python -m app.notify` once, or `--every 300` to keep running.

Schedule the one-shot form with cron (Linux) or the Task Scheduler (Windows).
"""
import argparse
import time

from .database import SessionLocal
from .mailer import default_mailer
from .services.notifications import send_alerts
from .timeutils import utcnow


def run_once() -> int:
    with SessionLocal() as db:
        return send_alerts(db, default_mailer(), utcnow())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--every', type=int, metavar='SEGUNDOS', help='repete a verificação nesse intervalo')
    args = parser.parse_args()
    while True:
        print(f'{utcnow():%Y-%m-%d %H:%M:%S} UTC · avisos enviados: {run_once()}', flush=True)
        if not args.every:
            break
        time.sleep(args.every)


if __name__ == '__main__':
    main()
