"""
Versi sync dari router, khusus dipakai termux_bot.py.

Beda dari src/router.py (yang pakai library `openai` + async): di sini
panggil tiap provider langsung pakai `requests.post`, karena semua provider
di config kompatibel format REST OpenAI (endpoint /chat/completions, body
dan response JSON-nya sama persis). Ini sengaja dibikin biar tidak perlu
install library `openai` (yang narik pydantic_core, sering gagal compile
di Termux) -- cukup `requests` yang ringan dan gampang diinstall di HP.

Logic fallback-nya sama persis dengan router.py: coba key demi key dalam
satu provider, kalau semua key provider itu habis baru pindah provider
berikutnya sesuai urutan.
"""

import logging
import time

import requests
import yaml

from src.key_pool import KeyPool

logger = logging.getLogger("router_sync")


class AllProvidersExhaustedError(Exception):
    pass


class SyncProviderRouter:
    def __init__(self, config_path: str, env: dict, state_dir: str = "data"):
        with open(config_path) as f:
            config = yaml.safe_load(f)

        self.tiers = []
        for t in config["tiers"]:
            keys = [env.get(name, "") for name in t["api_keys_env"]]
            pool = KeyPool(t["name"], keys, state_dir=state_dir)
            if not pool.has_keys():
                logger.warning("Provider '%s' dilewati: key kosong di .env", t["name"])
                continue
            self.tiers.append(
                {"name": t["name"], "base_url": t["base_url"].rstrip("/"), "model": t["model"], "pool": pool}
            )

        if not self.tiers:
            raise RuntimeError("Tidak ada provider dengan API key valid. Isi minimal satu di .env")

    def _resolve_routing(self, routing):
        if routing is None:
            return list(self.tiers)
        by_name = {t["name"]: t for t in self.tiers}
        resolved = []
        for entry in routing:
            tier_name, _, override_model = entry.partition(":")
            tier = by_name.get(tier_name)
            if tier is None:
                continue
            resolved.append({**tier, "model": override_model if override_model else tier["model"]})
        return resolved

    def chat(self, messages: list[dict], routing: list[str] | None = None, timeout: int = 60) -> tuple[str, str]:
        for tier in self._resolve_routing(routing):
            pool: KeyPool = tier["pool"]

            while True:
                key = pool.get_active_key()
                if key is None:
                    logger.info("Provider '%s' semua key cooldown, lanjut provider berikut.", tier["name"])
                    break

                url = f"{tier['base_url']}/chat/completions"
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"model": tier["model"], "messages": messages}

                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                except requests.RequestException as e:
                    logger.warning("Provider '%s' error koneksi (%s), coba key lain.", tier["name"], e)
                    pool.mark_exhausted(key, cooldown_seconds=300)
                    continue

                if resp.status_code == 200:
                    data = resp.json()
                    pool.mark_ok(key)
                    return data["choices"][0]["message"]["content"], tier["name"]

                if resp.status_code == 429:
                    logger.warning("Provider '%s' rate limit, rotate key.", tier["name"])
                    pool.mark_exhausted(key, cooldown_seconds=3600)
                    continue

                if resp.status_code == 404:
                    logger.error(
                        "Model '%s' di provider '%s' return 404 -- cek nama model masih aktif atau tidak.",
                        tier["model"], tier["name"],
                    )
                    break  # skip seluruh provider ini, jangan buang key lain

                logger.warning(
                    "Provider '%s' error HTTP %s: %s", tier["name"], resp.status_code, resp.text[:200]
                )
                pool.mark_exhausted(key, cooldown_seconds=300)
                continue

        raise AllProvidersExhaustedError(
            "Semua provider di daftar fallback sedang habis kuota/limit. Coba lagi nanti."
        )

