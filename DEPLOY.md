# Panduan Deploy Gratis ke Render

> **Koreksi (Juli 2026):** setelah dicek ulang, Render ternyata SEKARANG
> minta verifikasi kartu buat bikin Web Service, meski tetap disebut
> "free tier" (dikonfirmasi staff Render sendiri di forum komunitas
> mereka). Panduan di bawah ini jadi tidak lagi 100% "tanpa kartu".
>
> Kalau mau opsi yang beneran tanpa kartu sama sekali, pakai
> [`TERMUX.md`](./TERMUX.md) -- jalan langsung di HP Android, tidak ada
> hosting pihak ketiga sama sekali. Panduan Render ini dibiarkan di sini
> buat referensi kalau nanti mau pindah ke hosting cloud beneran (dan
> tidak keberatan verifikasi kartu).

Ditulis Juli 2026. Kebijakan free-tier platform hosting suka berubah tiap
beberapa bulan -- kalau ada langkah yang tidak cocok lagi sama tampilan
aslinya, itu tandanya platformnya ganti kebijakan, cek halaman pricing
resminya sebelum lanjut.

## Kenapa Render, bukan yang lain

Sempat dicek beberapa opsi lain, ini alasannya dicoret satu-satu:

- **Railway**: dulu free tier-nya generous, sekarang cuma kasih $1 kredit/bulan
  setelah bulan pertama -- tidak cukup buat nyalain servis 24 jam. Butuh
  upgrade $5/bulan buat itu.
- **Fly.io**: laporan soal kebijakan free tier-nya simpang siur (ada yang
  bilang masih dapat beberapa VM gratis, ada yang bilang sekarang wajib kartu
  dari awal). Karena tidak konsisten, dilewat dulu.
- **PythonAnywhere**: sebenarnya tidak butuh kartu dan web app-nya tidak
  "tidur" kayak Render. TAPI, free tier PythonAnywhere batasi internet
  keluar cuma ke situs yang di-whitelist -- untungnya Gemini, Groq, Cerebras,
  dan Anthropic semua sudah ke-whitelist, begitu juga `api.telegram.org`.
  Masalahnya ada laporan berulang soal `aiogram` (library yang dipakai di
  project ini) suka error `Network is unreachable` di PythonAnywhere karena
  library `aiohttp` di baliknya tidak otomatis lewat proxy whitelist itu,
  perlu konfigurasi proxy manual yang agak berbelit. Kalau mau coba jalur
  ini tetap bisa, tapi bukan yang paling mulus buat pemula, jadi Render
  ditaruh di depan.
- **Render**: internet keluar bebas (tidak ada whitelist), tidak minta kartu
  buat free tier, dan dokumentasinya paling jelas. Trade-off-nya cuma satu:
  servis gratis "tidur" kalau 15 menit tidak ada trafik, jadi pesan pertama
  setelah sepi bakal kejawab agak lambat (biasanya di bawah 1 menit) sebelum
  servisnya "bangun". Setelah itu balik cepat. Buat bot personal/kelas kecil,
  ini trade-off yang masuk akal.

## Langkah 1 -- Siapkan kode di GitHub

1. Bikin akun GitHub kalau belum punya (gratis, tidak perlu kartu).
2. Bikin repository baru, **private** juga tidak masalah (Render bisa akses
   repo private kalau kamu authorize).
3. Upload semua isi folder project ini ke repo itu. Cara paling gampang
   kalau belum biasa pakai `git`: buka repo di web GitHub -> "Add file" ->
   "Upload files" -> drag semua file/folder kecuali `.env` (jangan pernah
   upload `.env` asli, isinya key rahasia) dan folder `data/`.
4. Project ini sudah punya `.gitignore` yang nge-block `.env` dan `data/`
   supaya tidak ketarik ke GitHub -- pastikan file itu ikut keupload juga.

## Langkah 2 -- Bikin akun Render

1. Buka [render.com](https://render.com), daftar pakai email atau akun
   GitHub langsung (lebih gampang, otomatis nyambung buat langkah 3).
2. Tidak akan diminta kartu di langkah pendaftaran buat free tier.

## Langkah 3 -- Deploy sebagai Web Service

1. Di dashboard Render, klik **New +** -> **Web Service**.
2. Pilih **Build and deploy from a Git repository**, connect ke repo GitHub
   yang tadi dibuat.
3. Isi konfigurasi:
   - **Name**: bebas, misal `bot-maba-ti`
   - **Region**: pilih yang paling dekat (Singapore kalau ada)
   - **Branch**: `main` (atau branch default repomu)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python webhook_app.py`
   - **Instance Type**: pilih **Free**
4. Scroll ke bagian **Environment Variables**, klik **Add Environment
   Variable** satu-satu buat SEMUA isi `.env` kamu (bukan file-nya yang
   diupload, tapi isinya di-copy manual ke sini satu per satu):
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY_1`, `GROQ_API_KEY_1`, `OPENROUTER_API_KEY_1`, dst
   - `ADMIN_USERNAMES`
   - `WEBHOOK_HOST` -> isi belakangan (lihat langkah 4, butuh tahu URL Render
     dulu, yang baru muncul setelah service pertama kali dibuat)
5. Klik **Create Web Service**. Render mulai build otomatis.

## Langkah 4 -- Isi WEBHOOK_HOST setelah URL muncul

1. Setelah build selesai, Render kasih URL publik di bagian atas dashboard
   service kamu, bentuknya `https://bot-maba-ti-xxxx.onrender.com`.
2. Copy URL itu, balik ke tab **Environment**, isi variable `WEBHOOK_HOST`
   dengan URL itu (tanpa slash di akhir).
3. Klik **Save Changes** -- Render otomatis restart service dengan env
   variable yang baru. Saat startup, `webhook_app.py` otomatis daftarin
   webhook itu ke Telegram (lihat fungsi `on_startup` di kodenya), jadi
   tidak perlu jalanin `setWebhook` manual.

## Langkah 5 -- Tes

1. Buka bot di Telegram, kirim `/start`.
2. Kalau baru pertama kali (servis baru "bangun"), balasan bisa telat
   sampai ~1 menit. Setelah itu harusnya responsif.
3. Kalau tidak ada balasan sama sekali, cek log-nya: dashboard Render ->
   tab **Logs** -> cari error. Yang paling sering:
   - `KeyError: 'TELEGRAM_BOT_TOKEN'` -> env variable belum keisi/typo nama.
   - `KeyError: 'WEBHOOK_HOST'` -> langkah 4 belum dilakukan.
   - Bot diam tapi log bersih -> cek webhook manual lewat browser:
     `https://api.telegram.org/bot<TOKEN>/getWebhookInfo` (ganti `<TOKEN>`
     dengan token botmu) -- field `url` harus keisi otomatis sesuai
     WEBHOOK_HOST + `/webhook`, dan `last_error_message` (kalau ada)
     ngasih tahu masalahnya.

## Soal "tidur" nya free tier

Setelah 15 menit tidak ada request masuk, servis Render free otomatis
tidur. Ini bukan bug. Efeknya cuma delay di pesan pertama setelah sepi.
Kalau mau dikurangi (opsional, bukan wajib): pasang free uptime-monitor
seperti [cron-job.org](https://cron-job.org) atau UptimeRobot buat nge-ping
`https://bot-maba-ti-xxxx.onrender.com/` tiap 10 menit. Ini trik yang umum
dipakai, tapi bukan garansi resmi dari Render -- kalau kebijakan mereka
berubah dan ini diblokir, servis balik ke perilaku tidur normal, tidak
sampai bikin bot rusak permanen.

## Kalau nanti butuh lebih dari free tier

Kalau botnya makin ramai dan delay "bangun" mulai kerasa mengganggu,
opsi upgrade termurah yang jelas (Juli 2026): Render Starter $7/bulan
(hilang total sleep-nya) atau pindah ke VPS murah (Hetzner/DigitalOcean,
~$4-6/bulan, butuh kartu, tapi kendali penuh). Tidak wajib sekarang --
cuma dicatat di sini biar tidak kaget kalau nanti perlu.
