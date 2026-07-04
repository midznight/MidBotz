"""
Entry point KHUSUS buat Termux (Android). Jalankan: python termux_bot.py

Sengaja tidak pakai aiogram atau library `openai` -- keduanya narik
dependency yang sering gagal di-compile di Termux (aiohttp, pydantic_core).
Di sini cuma pakai `requests`, jauh lebih ringan dan gampang diinstall.

Cara kerja: long-polling manual ke endpoint getUpdates Telegram (mirip
prinsipnya sama seperti bot.py, cuma tanpa framework aiogram).
"""

import json
import logging
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
import requests

from src.router_sync import SyncProviderRouter, AllProvidersExhaustedError
from src.history import HistoryStore
from src.skills import SkillRegistry

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("termux_bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
ADMIN_USERNAMES = {u.strip().lower() for u in os.environ.get("ADMIN_USERNAMES", "").split(",") if u.strip()}
OFFSET_FILE = Path("data/telegram_offset.json")
VALID_AGENT_NAME = re.compile(r"^[a-z0-9_-]{2,32}$")

router = SyncProviderRouter("config/providers.yaml", env=os.environ)
history = HistoryStore()
skills = SkillRegistry()

# State admin /addagent sederhana, di memory. Kalau skrip di-restart di
# tengah proses /addagent, adminnya cukup ulang dari /addagent lagi.
pending_addagent: dict[int, str] = {}  # user_id -> nama_agent yang lagi dibikin


def send_message(chat_id: int, text: str):
    try:
        requests.post(f"{API_BASE}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=30)
    except requests.RequestException:
        logger.exception("Gagal kirim pesan ke %s", chat_id)


def send_typing(chat_id: int):
    try:
        requests.post(f"{API_BASE}/sendChatAction", json={"chat_id": chat_id, "action": "typing"}, timeout=10)
    except requests.RequestException:
        pass  # bukan hal fatal kalau gagal, cuma indikator visual


def load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return json.loads(OFFSET_FILE.read_text())["offset"]
        except (json.JSONDecodeError, KeyError):
            return 0
    return 0


def save_offset(offset: int):
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(json.dumps({"offset": offset}))


def is_admin(username: str | None) -> bool:
    return bool(username) and username.lower() in ADMIN_USERNAMES


def handle_command(text: str, user_id: int, username: str | None) -> bool:
    """Return True kalau text ditangani sebagai command (tidak perlu lempar ke AI)."""
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/start":
        send_message(
            user_id,
            "Halo! Aku asisten AI buat bantu maba Teknik Informatika.\n"
            "Tanya apa aja soal materi kuliah, tugas, atau dasar-dasar ngoding.\n\n"
            "Command lain:\n"
            "/reset - hapus histori chat kamu\n"
            "/agent - lihat/ganti agent aktif (ada 'coding' buat kerjaan kode)\n"
            "/addagent - admin only, bikin agent baru tanpa edit file",
        )
        return True

    if cmd == "/reset":
        history.clear(user_id)
        send_message(user_id, "Histori chat kamu udah dihapus, mulai dari nol lagi.")
        return True

    if cmd == "/agent":
        if not arg:
            current = history.get_agent(user_id)
            available = ", ".join(skills.list_names())
            send_message(user_id, f"Agent aktif: {current}\nPilihan lain: {available}\n\nGanti: /agent <nama>")
            return True
        if arg not in skills.list_names():
            send_message(user_id, f"Agent '{arg}' tidak ada. Pilihan: {', '.join(skills.list_names())}")
            return True
        history.set_agent(user_id, arg)
        send_message(user_id, f"Agent diganti ke '{arg}'.")
        return True

    if cmd == "/addagent":
        if not is_admin(username):
            send_message(user_id, "Command ini cuma buat admin.")
            return True
        if not arg:
            send_message(user_id, "Format: /addagent <nama_singkat>")
            return True
        agent_name = arg.lower()
        if not VALID_AGENT_NAME.match(agent_name):
            send_message(user_id, "Nama agent cuma boleh huruf kecil, angka, - atau _, 2-32 karakter.")
            return True
        if agent_name in skills.list_names():
            send_message(user_id, f"Agent '{agent_name}' sudah ada. Pilih nama lain.")
            return True
        pending_addagent[user_id] = agent_name
        send_message(
            user_id,
            f"Oke. Kirim system prompt buat agent '{agent_name}' di pesan berikutnya. Ketik /cancel buat batal.",
        )
        return True

    if cmd == "/cancel" and user_id in pending_addagent:
        del pending_addagent[user_id]
        send_message(user_id, "Dibatalkan.")
        return True

    return False


def handle_message(text: str, user_id: int, username: str | None):
    # Lagi di tengah proses /addagent? Pesan ini dianggap system prompt-nya.
    if user_id in pending_addagent:
        agent_name = pending_addagent.pop(user_id)
        skills.add_agent(name=agent_name, system_prompt=text, display_name=agent_name)
        send_message(user_id, f"Agent '{agent_name}' dibuat. Siapa pun bisa pakai: /agent {agent_name}")
        return

    if text.startswith("/"):
        if handle_command(text, user_id, username):
            return
        send_message(user_id, "Command tidak dikenal. Ketik /start buat lihat daftar command.")
        return

    agent_name = history.get_agent(user_id)
    history.add_message(user_id, "user", text)
    messages = [{"role": "system", "content": skills.system_prompt(agent_name)}] + history.get_recent(user_id)

    send_typing(user_id)
    try:
        reply, provider_used = router.chat(messages, routing=skills.routing(agent_name))
    except AllProvidersExhaustedError:
        send_message(user_id, "Maaf, semua provider AI gratis lagi kena limit bareng-bareng. Coba lagi nanti.")
        return
    except Exception:
        logger.exception("Error tak terduga waktu panggil AI")
        send_message(user_id, "Ada error pas proses jawaban. Coba kirim ulang pesannya.")
        return

    history.add_message(user_id, "assistant", reply)
    logger.info("User %s dijawab pakai provider: %s", user_id, provider_used)
    send_message(user_id, reply)


def main():
    offset = load_offset()
    logger.info("Bot jalan (mode Termux/polling). Tekan Ctrl+C buat berhenti.")

    while True:
        try:
            resp = requests.get(
                f"{API_BASE}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
            )
            resp.raise_for_status()
            result = resp.json().get("result", [])
        except requests.RequestException:
            logger.exception("Gagal ambil update, coba lagi 5 detik lagi.")
            time.sleep(5)
            continue

        for update in result:
            offset = update["update_id"] + 1
            save_offset(offset)

            message = update.get("message")
            if not message or "text" not in message:
                continue  # skip foto/stiker/dll, project ini cuma tangani teks

            user_id = message["from"]["id"]
            username = message["from"].get("username")
            try:
                handle_message(message["text"], user_id, username)
            except Exception:
                logger.exception("Error tak terduga waktu proses pesan dari %s", user_id)


if __name__ == "__main__":
    main()
