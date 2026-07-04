# Telegram AI Orchestrator

Bot Telegram yang manggil beberapa AI model gratis sebagai satu output, dengan
backup otomatis kalau salah satu provider/key kena limit.

## Struktur

```
bot.py                    entry point, handler Telegram
config/providers.yaml     daftar provider + urutan fallback
config/agents/*.yaml      persona/skill tiap agent (nambah agent = tambah file)
src/router.py             logic coba provider+key sampai ada yang jawab
src/key_pool.py           kelola beberapa API key per provider
src/history.py            riwayat chat per user, simpan di SQLite
src/skills.py             baca file agent jadi system prompt
data/                     isi otomatis: history.db, status cooldown key
```

## Setup

1. Python 3.11+, lalu:
   ```
   pip install -r requirements.txt
   ```
2. Copy `.env.example` jadi `.env`, isi `TELEGRAM_BOT_TOKEN` (minta dari
   [@BotFather](https://t.me/BotFather) di Telegram).
3. Ambil API key gratis (tanpa kartu kredit) dari provider yang mau dipakai,
   isi ke `.env`. Minimal isi satu provider biar bot bisa jalan:
   - Gemini: ai.google.dev -> Get API Key
   - Groq: console.groq.com -> API Keys
   - OpenRouter: openrouter.ai/keys (banyak model `:free` lewat satu key ini)
   - Cerebras: cloud.cerebras.ai -> API Keys
4. Mau nambah kapasitas: bikin akun baru di provider yang sama, isi key
   ke slot `_2`/`_3` di `.env`. Tidak perlu ubah kode.
5. Jalankan:
   ```
   python bot.py
   ```

## Nambah agent baru

**Cara 1 -- lewat Telegram, tanpa restart (admin only):**
```
/addagent nama_agent
```
Bot bakal minta system prompt di pesan berikutnya. Kirim, selesai -- semua
user langsung bisa pakai `/agent nama_agent`. Butuh username kamu ada di
`ADMIN_USERNAMES` di `.env`.

**Cara 2 -- manual lewat file (kalau butuh atur `routing` custom kayak
agent `coding`):** copy `config/agents/default.yaml`, ganti `name`,
`display_name`, `system_prompt`-nya (dan `routing` kalau perlu urutan
provider khusus), simpan file baru di folder yang sama, restart bot.
`/addagent` dari Telegram belum bisa atur `routing` custom, cuma system
prompt polos pakai urutan provider default.

## Soal Claude

Claude ditambahkan sebagai tier **opsional**, dipakai khusus oleh agent
`coding`. Penting buat dipahami sebelum isi key-nya: Claude **tidak**
punya kuota gratis harian yang isi ulang sendiri kayak Gemini/Groq/
OpenRouter/Cerebras. Yang ada cuma kredit trial sekali pakai (~$5) per
akun baru di [console.anthropic.com](https://console.anthropic.com) --
butuh verifikasi nomor HP, tidak butuh kartu. Begitu kredit itu habis,
key itu berhenti jalan sampai ditambah billing (yang berarti bayar).

Isi `CLAUDE_API_KEY_1` di `.env` dengan key dari akunmu sendiri kalau
mau coba, biarkan slot 2-5 kosong. **Jangan** bikin banyak akun cuma buat
ngumpulin kredit trial berulang kali -- itu penyalahgunaan promo dan
melanggar ketentuan layanan Anthropic. Kalau key Claude habis atau tidak
diisi sama sekali, agent `coding` otomatis lanjut ke Qwen3 Coder 480B
(gratis, lewat OpenRouter) yang memang kuat buat kerjaan kode -- bot tetap
jalan normal tanpa Claude.

## Deploy 24/7 gratis

- **Di HP Android sendiri (disarankan, paling minim kendala)**: lihat
  [`DEPLOY-TERMUX.md`](./DEPLOY-TERMUX.md) -- pakai Termux, tanpa kartu,
  tanpa whitelist internet, panduan lengkap step by step.
- **Di cloud**: lihat [`DEPLOY.md`](./DEPLOY.md). Catatan: bagian Render di
  situ sudah tidak akurat (Render sekarang minta verifikasi kartu), lagi
  disiapin gantinya.

## Catatan penting

- **Rate limit provider gratis suka berubah** tanpa pemberitahuan (pernah
  kejadian Groq dan Cerebras motong kuota mendadak). Kalau satu tier sering
  gagal terus, cek dulu dokumentasi resmi provider itu sebelum curiga ke kode.
- **Privasi**: sebagian provider gratis (misal Gemini, Mistral tier tertentu)
  memakai isi chat buat training model mereka kecuali kamu di EU/UK. Kalau
  bot ini bakal dipakai buat curhat/data pribadi mahasiswa, baca kebijakan
  data tiap provider dulu.
- Histori chat sekarang cuma window N pesan terakhir (lihat
  `MAX_TURNS_DEFAULT` di `src/history.py`), belum ada ringkasan otomatis
  buat percakapan sangat panjang. Cukup buat pemakaian normal, tapi kalau
  nanti mau chat sangat panjang tanpa lupa konteks lama, ini titik yang
  perlu ditambah (misal: ringkas otomatis pesan lama pakai AI juga).
- Command admin buat nambah **provider** baru (bukan cuma agent) lewat chat
  belum ada -- sekarang provider diedit manual di `config/providers.yaml`.
  Bisa ditambah kalau perlu.
