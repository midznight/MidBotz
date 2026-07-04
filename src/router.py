"""
ProviderRouter: inti dari sistem backup-antar-AI.

Alur chat():
1. Ambil tier provider pertama (sesuai urutan di config/providers.yaml).
2. Ambil key aktif dari KeyPool provider itu.
3. Panggil model. Kalau sukses -> selesai, balikin jawaban.
4. Kalau gagal karena limit/quota -> istirahatkan key itu, coba key
   berikutnya di provider yang sama.
5. Kalau semua key provider itu habis -> pindah ke provider berikutnya.
6. Kalau semua provider habis -> lempar error (AllProvidersExhaustedError).

Semua provider di config diasumsikan kompatibel format OpenAI (base_url beda,
tapi bentuk request/response sama), jadi cukup satu client class untuk semua.
"""

import logging
import yaml
from openai import AsyncOpenAI, RateLimitError, APIStatusError

from src.key_pool import KeyPool

logger = logging.getLogger("router")


class AllProvidersExhaustedError(Exception):
    pass


class ProviderRouter:
    def __init__(self, config_path: str, env: dict, state_dir: str = "data"):
        with open(config_path) as f:
            config = yaml.safe_load(f)

        self.tiers = []
        for tier in config["tiers"]:
            keys = [env.get(name, "") for name in tier["api_keys_env"]]
            pool = KeyPool(tier["name"], keys, state_dir=state_dir)
            if not pool.has_keys():
                logger.warning(
                    "Provider '%s' dilewati: belum ada API key diisi di .env",
                    tier["name"],
                )
                continue
            self.tiers.append(
                {
                    "name": tier["name"],
                    "base_url": tier["base_url"],
                    "model": tier["model"],
                    "pool": pool,
                }
            )

        if not self.tiers:
            raise RuntimeError(
                "Tidak ada provider dengan API key valid. Isi minimal satu di .env"
            )

    def _resolve_routing(self, routing: list[str] | None) -> list[dict]:
        """
        routing=None -> pakai urutan default semua tier (perilaku lama, tidak berubah).
        routing=["claude", "openrouter:qwen/qwen3-coder-480b:free", "groq"] -> tiap
        entry dicocokkan ke tier yang sudah dikonfigurasi; tier tanpa key valid
        (tidak ke-load di __init__) otomatis kelewat. Override model pakai
        "nama_tier:nama_model" -- split cuma di titik dua PERTAMA, jadi model id
        yang mengandung ":" sendiri (contoh openrouter punya suffix ":free") aman.
        """
        if routing is None:
            return [{"name": t["name"], "base_url": t["base_url"], "model": t["model"], "pool": t["pool"]} for t in self.tiers]

        by_name = {t["name"]: t for t in self.tiers}
        resolved = []
        for entry in routing:
            tier_name, _, override_model = entry.partition(":")
            tier = by_name.get(tier_name)
            if tier is None:
                continue  # tier tidak dikonfigurasi (key kosong) -- skip diam-diam
            resolved.append(
                {
                    "name": tier["name"],
                    "base_url": tier["base_url"],
                    "model": override_model if override_model else tier["model"],
                    "pool": tier["pool"],
                }
            )
        return resolved

    async def chat(self, messages: list[dict], routing: list[str] | None = None) -> tuple[str, str]:
        """
        Kembalikan (isi_jawaban, nama_provider_yang_jawab).
        routing: urutan tier khusus buat agent tertentu (lihat _resolve_routing).
        None = pakai urutan default config/providers.yaml.
        """
        for tier in self._resolve_routing(routing):
            pool: KeyPool = tier["pool"]

            while True:
                key = pool.get_active_key()
                if key is None:
                    logger.info("Provider '%s' semua key cooldown, lanjut ke provider berikut.", tier["name"])
                    break  # provider ini habis, coba provider berikutnya

                client = AsyncOpenAI(api_key=key, base_url=tier["base_url"])
                try:
                    resp = await client.chat.completions.create(
                        model=tier["model"],
                        messages=messages,
                    )
                    pool.mark_ok(key)
                    return resp.choices[0].message.content, tier["name"]

                except RateLimitError:
                    logger.warning("Key di provider '%s' kena rate limit, rotate key.", tier["name"])
                    pool.mark_exhausted(key, cooldown_seconds=3600)
                    continue  # coba key lain di provider yang sama

                except APIStatusError as e:
                    if e.status_code == 404:
                        # kemungkinan nama model sudah tidak aktif di provider ini
                        logger.error(
                            "Model '%s' di provider '%s' return 404. "
                            "Cek apakah nama model masih ada di dokumentasi provider.",
                            tier["model"], tier["name"],
                        )
                        break  # jangan buang-buang key lain, langsung skip provider ini
                    logger.warning(
                        "Provider '%s' error %s, istirahatkan key sebentar.",
                        tier["name"], e.status_code,
                    )
                    pool.mark_exhausted(key, cooldown_seconds=300)
                    continue

        raise AllProvidersExhaustedError(
            "Semua provider di daftar fallback sedang habis kuota/limit. Coba lagi nanti."
        )
