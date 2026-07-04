# Panduan Deploy di Termux (Android)

Ditulis Juli 2026. Jalan di HP sendiri: gratis 100%, tidak ada hosting,
tidak ada kartu, tidak ada whitelist internet. Trade-off-nya: HP harus
nyala & connect internet terus buat bot-nya "online".

**Pakai `termux_bot.py`, BUKAN `bot.py`.** `bot.py` pakai `aiogram`, yang
di dalamnya butuh compile `aiohttp` dan `pydantic_core` (Rust) -- ini
sumber #1 orang stuck di Termux, banyak laporan gagal di forum resmi
aiogram maupun Termux, kadang perlu setup toolchain Rust yang ribet dan
tetap gagal karena masalah permission compiler. `termux_bot.py` sengaja
dibikin cuma pakai `requests`, yang tidak butuh compile apapun.

## Langkah 1 -- Install Termux (BUKAN dari Play Store)

Versi Termux di Google Play Store sudah lama tidak di-update dan banyak
yang rusak. Install dari **F-Droid**:

1. Buka [f-droid.org](https://f-droid.org) di browser HP, download & install
   aplikasi F-Droid (APK, perlu izinkan "install dari sumber tidak dikenal"
   sekali di setting Android).
2. Buka F-Droid, cari "Termux", install.
3. (Opsional tapi disaranin) install juga **Termux:Boot** dari F-Droid --
   dipakai nanti kalau mau bot auto-jalan tiap HP restart.

## Langkah 2 -- Setup dasar Termux

Buka aplikasi Termux, ketik satu-satu (Enter tiap baris):

```
pkg update -y && pkg upgrade -y
pkg install -y python git unzip nano
```

Kalau ada pertanyaan "Configuration file... keep the local version?" pas
`pkg upgrade`, pilih **N** (pakai versi baru) kecuali kamu tahu persis
kenapa mau pertahankan versi lama.

Cek python sudah kepasang:
```
python --version
```
Harus muncul versi Python (3.x apapun, tidak masalah karena `termux_bot.py`
tidak pakai library yang rewel soal versi Python).

## Langkah 3 -- Ambil kode project ke HP

**Cara paling gampang** (kalau file zip project ada di Downloads HP, misal
dari link yang saya kasih di chat ini):

```
termux-setup-storage
```
Bakal muncul popup izin akses storage di Android, klik **Allow/Izinkan**.
Lanjut:
```
cd ~
cp ~/storage/downloads/telegram-ai-orchestrator.zip .
unzip telegram-ai-orchestrator.zip
cd telegram-ai-orchestrator
```

**Alternatif** (kalau kodenya sudah kamu push ke GitHub):
```
cd ~
git clone https://github.com/username-kamu/nama-repo.git telegram-ai-orchestrator
cd telegram-ai-orchestrator
```

## Langkah 4 -- Install dependency

**PENTING**: pakai file `requirements-termux.txt`, jangan `requirements.txt`
biasa (itu punya `aiogram`+`openai` yang bermasalah di Termux).

```
pip install -r requirements-termux.txt
```

Proses ini seharusnya cepat dan tanpa compile apapun (semua isinya pure
Python/sudah ada wheel siap pakai). Kalau ada error di sini, screenshot
error paling atasnya -- itu petunjuk paling akurat masalahnya di mana.

## Langkah 5 -- Isi konfigurasi

```
cp .env.example .env
nano .env
```

Isi minimal `TELEGRAM_BOT_TOKEN` dan satu API key AI (misal
`GEMINI_API_KEY_1`). Cara pakai `nano`: edit langsung kayak notepad,
selesai tekan `Ctrl+X`, lalu `Y`, lalu `Enter` buat simpan.

## Langkah 6 -- Jalankan

```
python termux_bot.py
```

Kalau muncul log `Bot jalan (mode Termux/polling)`, coba buka bot-nya di
Telegram, kirim `/start`. Harus langsung dibalas (tidak ada cold-start
kayak hosting gratis, karena ini jalan langsung di HP).

Berhenti: `Ctrl+C`.

## Langkah 7 -- Biar tetap jalan pas HP dikunci/app ditutup

Ini bagian yang paling sering bikin bingung, jadi dirinci:

1. **Android suka "membunuh" app di background buat hemat baterai.**
   Ke Setting Android -> Apps -> Termux -> Battery -> pilih **Unrestricted**
   / matikan "battery optimization" khusus buat Termux. Tanpa ini,
   Android bisa mem-freeze proses `python termux_bot.py` walau Termux-nya
   masih kelihatan "terbuka".

2. **Tetap butuh sesi yang tidak mati kalau layar HP dikunci.** Install
   `tmux` biar proses tetap jalan walau kamu keluar dari aplikasi Termux:
   ```
   pkg install -y tmux
   tmux new -s bot
   python termux_bot.py
   ```
   Keluar dari sesi tmux TANPA mematikan bot: tekan `Ctrl+B` lalu `D`
   (bukan `Ctrl+C`, itu bakal matiin bot-nya). Bot tetap jalan di
   background. Buat balik lihat log-nya lagi kapan saja:
   ```
   tmux attach -t bot
   ```

3. **Ambil wakelock** biar Termux tidak ditidurkan sistem sama sekali
   selagi tmux jalan:
   ```
   termux-wake-lock
   ```
   Jalankan sekali, efeknya berlaku sampai kamu jalankan `termux-wake-unlock`
   atau restart HP.

4. **(Opsional) Auto-start pas HP restart.** Kalau sudah install
   Termux:Boot di Langkah 1, buat file:
   ```
   mkdir -p ~/.termux/boot
   nano ~/.termux/boot/start-bot.sh
   ```
   Isi:
   ```
   #!/data/data/com.termux/files/usr/bin/sh
   termux-wake-lock
   cd ~/telegram-ai-orchestrator
   python termux_bot.py >> bot.log 2>&1
   ```
   Simpan (`Ctrl+X`, `Y`, `Enter`), lalu:
   ```
   chmod +x ~/.termux/boot/start-bot.sh
   ```
   Sekarang tiap HP restart, bot otomatis jalan sendiri (butuh buka
   Termux:Boot sekali secara manual setelah instalasi biar Android kasih
   izinnya jalan pas boot).

## Troubleshooting

- **`pip install` masih coba compile sesuatu / muncul error clang** ->
  cek kamu beneran pakai `requirements-termux.txt`, bukan `requirements.txt`.
- **Bot tidak balas sama sekali, tidak ada error di layar** -> cek koneksi
  internet HP, dan cek token di `.env` benar (test manual di browser:
  `https://api.telegram.org/bot<TOKEN>/getMe` harus balikin info bot,
  bukan error).
- **Bot jalan lalu berhenti sendiri pas HP dikunci lama** -> berarti
  Langkah 7 (battery optimization + tmux + wake-lock) belum semua
  dilakukan. Cek satu-satu.
- **Baterai boros** -> wajar, bot jalan terus = HP kerja terus. Kalau mau
  hemat baterai, colok charger terus atau jadwalkan `termux_bot.py` cuma
  jalan pas jam tertentu (misal jam kuliah aktif).

## Batasannya dibanding hosting cloud

- HP harus nyala & connect internet -- kalau HP mati/mode pesawat/wifi
  putus, bot ikut mati (tidak ada redundansi otomatis kayak server cloud).
- Kalau HP dipakai buat hal lain yang berat/di-restart, bot ikut kena
  imbas. Buat pemakaian pribadi/testing/kelas kecil ini oke -- kalau
  nanti bot dipakai banyak orang serius, VPS murah ($4-6/bulan, butuh
  kartu) atau balik ke opsi hosting cloud lebih cocok.
