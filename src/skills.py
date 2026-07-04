"""
Baca semua file config/agents/*.yaml jadi daftar agent yang bisa dipilih user.

Nambah agent baru = taruh file .yaml baru di config/agents/, restart bot.
Tidak perlu ubah kode apapun di sini.
"""

from pathlib import Path
import yaml


class SkillRegistry:
    def __init__(self, agents_dir: str = "config/agents"):
        self.agents_dir = Path(agents_dir)
        self._agents = self._load_all()

    def _load_all(self) -> dict:
        agents = {}
        for path in self.agents_dir.glob("*.yaml"):
            with open(path) as f:
                data = yaml.safe_load(f)
            agents[data["name"]] = data
        return agents

    def list_names(self) -> list[str]:
        return list(self._agents.keys())

    def get(self, name: str) -> dict:
        return self._agents.get(name, self._agents["default"])

    def system_prompt(self, name: str) -> str:
        return self.get(name)["system_prompt"]

    def routing(self, name: str) -> list[str] | None:
        return self.get(name).get("routing")

    def add_agent(self, name: str, system_prompt: str, display_name: str | None = None) -> None:
        """Tulis file config/agents/<name>.yaml baru lalu muat ulang registry.
        Dipakai oleh command admin /addagent -- tidak perlu restart bot."""
        data = {
            "name": name,
            "display_name": display_name or name,
            "description": f"Ditambahkan lewat /addagent",
            "system_prompt": system_prompt,
        }
        path = self.agents_dir / f"{name}.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        self._agents = self._load_all()
