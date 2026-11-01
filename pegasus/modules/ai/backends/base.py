"""Backend contract."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenRes:
    text: str
    tokens: int = 0
    backend: str = ""
    model: str = ""


class Backend(ABC):
    name = "base"

    @abstractmethod
    async def load(self, repo: str, quant: str, ctx: int) -> None: ...

    @abstractmethod
    async def generate(self, prompt, grammar, temp, max_tokens, stop,
                       mode="constrained") -> GenRes: ...

    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def unload(self) -> None: ...

    def supports_grammar(self) -> bool:
        return True
