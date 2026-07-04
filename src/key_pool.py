"""
KeyPool: kelola beberapa API key untuk SATU provider.

Kenapa perlu ini: tiap provider gratisan biasanya limit-nya per API key
(request/menit, request/hari). Kalau kita punya 3 key (dari 3 akun berbeda),
kapasitas kita jadi 3x lipat -- KeyPool yang jaga urutan pakai key mana,
dan "istirahatkan" key yang baru kena limit tanpa kita mikirin manual.

State disimpan ke file JSON supaya kalau bot di-restart, key yang lagi
cooldown tidak langsung dipakai lagi sebelum waktunya.
"""

import json
import time
from pathlib import Path


class KeyPool:
    def __init__(self, provider_name: str, keys: list[str], state_dir: str = "data"):
        self.provider_name = provider_name
        self.keys = [k for k in keys if k]  # buang key kosong/None
        self.state_path = Path(state_dir) / f"keypool_{provider_name}.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_state(self):
        self.state_path.write_text(json.dumps(self._state))

    def has_keys(self) -> bool:
        return len(self.keys) > 0

    def get_active_key(self) -> str | None:
        """Kembalikan key pertama yang tidak lagi cooldown. None kalau semua habis."""
        now = time.time()
        for key in self.keys:
            info = self._state.get(key)
            if info is None:
                return key
            if info.get("cooldown_until", 0) <= now:
                return key
        return None

    def mark_exhausted(self, key: str, cooldown_seconds: int = 3600):
        """Panggil kalau key ini kena rate-limit/quota. Default istirahat 1 jam."""
        self._state[key] = {"cooldown_until": time.time() + cooldown_seconds}
        self._save_state()

    def mark_ok(self, key: str):
        """Panggil kalau call sukses, biar status cooldown-nya bersih."""
        if key in self._state:
            del self._state[key]
            self._save_state()

    def all_exhausted(self) -> bool:
        return self.has_keys() and self.get_active_key() is None
