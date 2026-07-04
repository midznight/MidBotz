"""
Entry point. Jalankan dengan: python bot.py

Alur tiap pesan masuk:
Telegram -> handler -> ambil histori + agent user dari HistoryStore
         -> susun messages[] (system prompt + histori + pesan baru)
         -> ProviderRouter.chat() -> coba tiap provider/key sampai ada yang jawab
         -> simpan jawaban ke histori -> balas ke user
"""

import asyncio
import logging
import os
import re

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from src.router import ProviderRouter, AllProvidersExhaustedError
from src.history import HistoryStore
from src.skills import SkillRegistry

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_USERNAMES = {u.strip() for u in os.environ.get("ADMIN_USERNAMES", "").split(",") if u.strip()}

router = ProviderRouter("config/providers.yaml", env=os.environ)
history = HistoryStore()
skills = SkillRegistry()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
# Catatan: MemoryStorage artinya state /addagent yang belum selesai hilang
# kalau bot di-restart. Untuk pemakaian pribadi/kelas kecil ini cukup --
# kalau butuh lebih awet, ganti ke RedisStorage.

VALID_AGENT_NAME = re.compile(r"^[a-z0-9_-]{2,32}$")


def is_admin(message: Message) -> bool:
    username = message.from_user.username or ""
    return username.lower() in {u.lower() for u in ADMIN_USERNAMES}


class AddAgentStates(StatesGroup):
    waiting_for_prompt = State()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Halo! Aku asisten AI buat bantu maba Teknik Informatika.\n"
        "Tanya apa aja soal materi kuliah, tugas, atau dasar-dasar ngoding.\n\n"
        "Command lain:\n"
        "/reset - hapus histori chat kamu\n"
        "/agent - lihat/ganti agent aktif (ada 'coding' buat kerjaan kode)\n"
        "/addagent - admin only, bikin agent baru tanpa edit file"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    history.clear(message.from_user.id)
    await message.answer("Histori chat kamu udah dihapus, mulai dari nol lagi.")


@dp.message(Command("agent"))
async def cmd_agent(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) == 1:
        current = history.get_agent(message.from_user.id)
        available = ", ".join(skills.list_names())
        await message.answer(f"Agent aktif: {current}\nPilihan lain: {available}\n\nGanti: /agent <nama>")
        return

    requested = args[1].strip()
    if requested not in skills.list_names():
        await message.answer(f"Agent '{requested}' tidak ada. Pilihan: {', '.join(skills.list_names())}")
        return

    history.set_agent(message.from_user.id, requested)
    await message.answer(f"Agent diganti ke '{requested}'.")


@dp.message(Command("addagent"))
async def cmd_addagent(message: Message, state: FSMContext):
    if not is_admin(message):
        await message.answer("Command ini cuma buat admin.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Format: /addagent <nama_singkat>\nContoh: /addagent basisdata")
        return

    agent_name = args[1].strip().lower()
    if not VALID_AGENT_NAME.match(agent_name):
        await message.answer("Nama agent cuma boleh huruf kecil, angka, - atau _, 2-32 karakter.")
        return
    if agent_name in skills.list_names():
        await message.answer(f"Agent '{agent_name}' sudah ada. Pilih nama lain.")
        return

    await state.update_data(agent_name=agent_name)
    await state.set_state(AddAgentStates.waiting_for_prompt)
    await message.answer(
        f"Oke. Kirim system prompt buat agent '{agent_name}' di pesan berikutnya "
        f"(boleh panjang/multi-baris). Ketik /cancel buat batal."
    )


@dp.message(Command("cancel"), StateFilter(AddAgentStates.waiting_for_prompt))
async def cmd_cancel_addagent(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Dibatalkan.")


@dp.message(StateFilter(AddAgentStates.waiting_for_prompt))
async def receive_agent_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    agent_name = data["agent_name"]
    skills.add_agent(name=agent_name, system_prompt=message.text, display_name=agent_name)
    await state.clear()
    await message.answer(
        f"Agent '{agent_name}' dibuat. Siapa pun bisa pakai: /agent {agent_name}"
    )


@dp.message()
async def handle_chat(message: Message):
    user_id = message.from_user.id
    agent_name = history.get_agent(user_id)
    system_prompt = skills.system_prompt(agent_name)

    history.add_message(user_id, "user", message.text)

    messages = [{"role": "system", "content": system_prompt}] + history.get_recent(user_id)

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        reply, provider_used = await router.chat(messages, routing=skills.routing(agent_name))
    except AllProvidersExhaustedError:
        await message.answer(
            "Maaf, semua provider AI gratis lagi kena limit bareng-bareng. "
            "Coba lagi beberapa menit ya."
        )
        return
    except Exception:
        logger.exception("Error tak terduga waktu panggil AI")
        await message.answer("Ada error pas proses jawaban. Coba kirim ulang pesannya.")
        return

    history.add_message(user_id, "assistant", reply)
    logger.info("User %s dijawab pakai provider: %s", user_id, provider_used)
    await message.answer(reply)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
