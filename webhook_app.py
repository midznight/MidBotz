"""
Entry point KHUSUS buat deploy ke hosting yang minta HTTP server (Render, dst).
Buat coba-coba di laptop sendiri, tetap pakai `python bot.py` (mode polling).

Bedanya: bot.py "narik" pesan terus-terusan ke Telegram (polling), cocok
buat lokal tapi hosting gratis kebanyakan cuma kasih slot buat "web service"
yang nunggu HTTP request masuk. Mode webhook di sini yang menjembatani itu:
Telegram yang "dorong" pesan baru ke URL publik kita lewat POST request.

Environment tambahan yang dibutuhkan (di luar yang dipakai bot.py):
  WEBHOOK_HOST   -> URL publik dari hosting-nya, contoh https://nama-app.onrender.com
  PORT           -> biasanya diisi otomatis sama platform hosting-nya

Jalankan: python webhook_app.py
"""

import os
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot import bot, dp

WEBHOOK_PATH = "/webhook"
WEBHOOK_HOST = os.environ["WEBHOOK_HOST"].rstrip("/")
PORT = int(os.environ.get("PORT", 10000))


async def on_startup(bot):
    await bot.set_webhook(f"{WEBHOOK_HOST}{WEBHOOK_PATH}")


async def health(request):
    # Endpoint kosong buat dicek platform hosting-nya (health check), dan
    # buat mastiin sendiri lewat browser bahwa prosesnya hidup.
    return web.Response(text="Bot jalan.")


def main():
    dp.startup.register(on_startup)

    app = web.Application()
    app.router.add_get("/", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
