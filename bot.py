"""
POLYBATTLE | OFFICIAL — bot do servidor Discord.

Uso:
    python bot.py            inicia o bot
    python bot.py --check    valida .env, blueprint e banco sem conectar ao Discord
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import logging.handlers
import sys

from core.config import ConfigError, Settings, load_settings


class _RedactToken(logging.Filter):
    """Garante que o token nunca apareça nos logs, mesmo em tracebacks."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token

    def filter(self, record: logging.LogRecord) -> bool:
        if self.token and self.token in record.getMessage():
            record.msg = record.getMessage().replace(self.token, "[TOKEN REMOVIDO]")
            record.args = ()
        return True


def setup_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_dir / "polybattle.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    console = logging.StreamHandler(sys.stdout)
    redact = _RedactToken(settings.token)
    for handler in (file_handler, console):
        handler.setFormatter(fmt)
        handler.addFilter(redact)
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    root.handlers[:] = [file_handler, console]
    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("discord.http").setLevel(logging.WARNING)


def run_check(settings: Settings) -> int:
    """Validação offline: blueprint, banco e configuração."""
    from core.blueprint import validate_blueprint
    from core.database import Database

    problems = validate_blueprint()
    for p in problems:
        print(f"[BLUEPRINT] {p}")
    db = Database(settings.database_path)
    db.connect_sync()
    asyncio.run(db.close())
    print(f"[OK] Banco: {settings.database_path}")
    print(f"[OK] Servidor alvo (GUILD_ID): {settings.guild_id or 'global'}")
    print("[OK] Blueprint consistente" if not problems else "[ERRO] Corrija o blueprint")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PolyBattle Discord bot")
    parser.add_argument("--check", action="store_true", help="valida a configuração sem conectar")
    args = parser.parse_args()

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"[CONFIG] {exc}", file=sys.stderr)
        return 2

    if args.check:
        return run_check(settings)

    setup_logging(settings)
    import discord
    from core.bot import PolyBattleBot

    bot = PolyBattleBot(settings)
    try:
        bot.run(settings.token, log_handler=None)
    except discord.LoginFailure:
        logging.getLogger("polybattle").critical("Token inválido. Gere um novo token no Developer Portal.")
        return 3
    except discord.PrivilegedIntentsRequired:
        logging.getLogger("polybattle").critical(
            "Ative as intents SERVER MEMBERS e MESSAGE CONTENT no Developer Portal (aba Bot).")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
