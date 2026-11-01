"""Provider chain with an even per-provider daily spend share."""
PRICE = {"openai": 0.15, "anthropic": 3.0, "groq": 0.05, "openrouter": 1.0,
         "venice": 0.5, "deepseek": 0.14, "local": 0.0}


class Chain:
    def __init__(self, names: list[str], daily_usd: float = 5.0):
        self.names = names
        self.cap = daily_usd
        self.spent: dict[str, float] = {}

    def _share(self) -> float:
        return self.cap / max(len(self.names), 1)

    def next(self) -> str | None:
        for name in self.names:
            if self.spent.get(name, 0.0) < self._share():
                return name
        return None

    def record(self, name: str, tokens: int) -> None:
        self.spent[name] = self.spent.get(name, 0.0) + tokens / 1e6 * PRICE.get(name, 1.0)

    def snapshot(self) -> dict:
        return {"cap": self.cap, "spent": {k: round(v, 3) for k, v in self.spent.items()},
                "remaining": round(self.cap - sum(self.spent.values()), 3)}
