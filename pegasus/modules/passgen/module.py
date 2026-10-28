"""
Pegasus Phantom Menace v2 - Passgen Module
Wordlist generator based on user-provided info with case, leet, separator, and numeric variations.
"""
from __future__ import annotations

import asyncio
import itertools
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from pegasus.modules.base import BaseModule
from pegasus.core.plugin import CommandInfo, PluginMetadata
from pegasus.core.config import get_settings


# ========================================================================
# Wordlist settings (mirroring Passgen defaults)
# ========================================================================
MAX_COMBO_TOKENS = 3
ADD_LEET = True
ADD_CASE_VARIANTS = True
ADD_SEPARATORS = True
ADD_NUM_TAILS = True
MIN_LEN = 7
MAX_LEN = 24
OUTPUT_FILE = "wordlist.txt"

LEET_MAP = str.maketrans({
    'a': '4', 'A': '4',
    'e': '3', 'E': '3',
    'i': '1', 'I': '1',
    'o': '0', 'O': '0',
    's': '5', 'S': '5',
    't': '7', 'T': '7',
    'b': '8', 'B': '8',
})

THEME = {
    "brand": "bold bright_white",
    "gradient_from": "bright_cyan",
    "gradient_to": "magenta",
    "panel_border": "bright_cyan",
    "panel_border_alt": "bright_magenta",
    "label": "bold bright_white",
    "muted": "grey62",
    "prompt": "bold bright_cyan",
    "input_hint": "grey70",
    "ok": "bold green",
    "warn": "bold yellow",
    "bad": "bold red",
    "accent": "bright_magenta",
}

try:
    from rich.console import Console as _Console
    from rich.panel import Panel as _Panel
    from rich.text import Text as _Text
    from rich.box import HEAVY as _HEAVY
    from rich.rule import Rule as _Rule
    from rich.table import Table as _Table
    RICH_OK = True
except Exception:
    RICH_OK = False


def _clean_token(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9A-Za-z._-]", "", s)
    return s


def _case_variants(s: str) -> Set[str]:
    variants = {s, s.lower(), s.upper()}
    if s:
        variants.add(s.capitalize())
    parts = re.split(r"[_\-.]", s)
    camel = ''.join(p.capitalize() for p in parts if p)
    if camel:
        variants.add(camel)
        variants.add(camel.lower())
    return variants


def _leet_variants(s: str) -> Set[str]:
    return {s, s.translate(LEET_MAP)}


def _with_separators(tokens: List[str]) -> Set[str]:
    if len(tokens) == 1:
        return {tokens[0]}
    seps = ['', '-', '_', '.'] if ADD_SEPARATORS else ['']
    out: Set[str] = set()
    if '' in seps:
        out.add(''.join(tokens))
    for sep in seps:
        out.add(sep.join(tokens))
    return out


def _add_numeric_tails(words: Set[str], tails: List[str]) -> Set[str]:
    out = set(words)
    for w in words:
        for t in tails:
            out.add(f"{w}{t}")
    return out


def _unique_len_filtered(words: Set[str]) -> Set[str]:
    return {w for w in set(words) if MIN_LEN <= len(w) <= MAX_LEN}


class PassgenModule(BaseModule):
    """
    Wordlist generator module.
    Generates custom wordlists from user-provided info (name, surname,
    nickname, team, date of birth) with case, leetspeak, separator,
    and numeric-tail variations.
    """

    metadata = PluginMetadata(
        name="passgen",
        version="2.0.0",
        description="Wordlist generator - custom wordlists from personal info with variations",
        author="Hexec",
        category="credentials",
        tags=["wordlist", "password", "generator", "bruteforce", "credentials", "wordlist-generator"],
        requires=["rich"],
        requires_python=">=3.9",
    )

    @property
    def module_name(self) -> str:
        return "Passgen"

    @property
    def module_description(self) -> str:
        return "Wordlist generator - custom wordlists from personal info with variations"

    @property
    def module_category(self) -> str:
        return "credentials"

    async def _register_commands(self) -> None:
        self.register_command("passgen", "Run wordlist generator wizard", self.cmd_passgen)
        self.register_command("passgen-config", "Show/passgen configuration", self.cmd_passgen_config)

    async def _register_ui_components(self) -> None:
        self.register_ui_component(
            name="passgen_dashboard",
            component_type="panel",
            path="/passgen",
            title="Passgen Wordlist Generator",
            icon="🔐",
            order=4,
        )

    async def _register_hooks(self) -> None:
        pass

    def _console_width(self) -> int:
        return shutil.get_terminal_size((80, 24)).columns

    def _show_banner(self) -> None:
        width = self._console_width()
        ascii_line = r"""
  ___  _   ___ ___  ___ ___ _  _ 
 | _ \/_\ / __/ __|/ __| __| \| |
 |  _/ _ \\__ \__ \ (_ | _|| .` |
 |_|/_/ \_\___/___/\___|___|_|\_|
"""
        if not RICH_OK:
            print()
            print(("== " + "HEXSEC" + " ==" + f"  [passgen]").center(width))
            print(("Telegram: hexsec_tools").center(width))
            print(ascii_line)
            print("-" * width)
            return

        brand_label = Text("HEXSEC", style=THEME["brand"])
        line_text = _Text(ascii_line)
        try:
            line_text.apply_gradient(THEME["gradient_from"], THEME["gradient_to"])
        except Exception:
            line_text.stylize(THEME["brand"])

        prog_panel = Panel(
            _Text("passgen", style=THEME["label"]),
            title="program",
            title_align="left",
            subtitle="ready",
            subtitle_align="right",
            border_style=THEME["panel_border"],
            box=_HEAVY,
            padding=(0, 4),
            width=min(40, max(28, width // 3)),
        )

        tg = _Text()
        tg.append("Telegram: ", style="bold bright_green")
        tg.append("hexsec_tools", style="bold bright_cyan")
        tg_panel = Panel(
            tg,
            box=_HEAVY,
            border_style=THEME["panel_border_alt"],
            padding=(0, 2),
            title="connect",
            title_align="left",
            subtitle="© hexsec",
            subtitle_align="right",
            width=min(max(34, len("Telegram: hexsec_tools") + 6), max(46, width // 2)),
        )

        self._console.print()
        self._console.print(brand_label, justify="center")
        self._console.print(line_text, justify="center", overflow="fold")
        self._console.print(prog_panel, justify="center")
        self._console.print(tg_panel, justify="center")
        self._console.print(Rule(style=THEME["muted"]))

    def _quick_help(self) -> None:
        if not RICH_OK:
            print("Quick start:")
            print("  1) Enter first/last name, optional nickname and team.")
            print("  2) Enter date as dd/mm/yyyy or ddmmyyyy.")
            print("  3) Variations (case/leet/separators) are generated.")
            print(f"  4) Output saved to '{OUTPUT_FILE}'.\n")
            return

        t = Table.grid(padding=(0, 1))
        t.add_column(justify="right", style=THEME["muted"])
        t.add_column()
        t.add_row("1.", "Fill in first name, last name, optional nickname and team.")
        t.add_row("2.", "Enter date as [bold]dd/mm/yyyy[/] or [bold]ddmmyyyy[/] (e.g., 01/01/1990).")
        t.add_row("3.", "Generator creates case, leet and separator variants.")
        t.add_row("4.", f"Output is saved to [bold]{OUTPUT_FILE}[/].")
        self._console.print(t)
        self._console.print(Rule(style=THEME["muted"]))

    def _styled_input(self, prompt: str, hint: str = "") -> str:
        if not RICH_OK:
            return input(f"{prompt} ").strip()
        hint_part = f" [dim]{hint}[/]" if hint else ""
        return self._console.input(f"[{THEME['prompt']}]{prompt}[/]{hint_part} ").strip()

    # ── Command Handlers ──────────────────────────────────────────────

    async def cmd_passgen(self, *args) -> None:
        """Run the Passgen wordlist generator wizard."""
        self._show_banner()
        self._quick_help()

        name = self._styled_input("First name:", "ASCII only")
        surname = self._styled_input("Last name:", "ASCII only")
        nickname = self._styled_input("Nickname:", "optional")
        team = self._styled_input("Team:", "optional")
        date_str = self._styled_input("Date:", "dd/mm/yyyy or ddmmyyyy")

        # Clean tokens
        tokens = [_clean_token(x) for x in [name, surname, nickname, team] if x.strip()]

        # Parse date
        date_tokens: Set[str] = set()
        if date_str:
            ds = re.sub(r"[^\d]", "", date_str)
            day = month = year = ""
            if len(ds) == 8:
                day, month, year = ds[:2], ds[2:4], ds[4:]
            elif len(ds) == 6:  # ddmmyy
                day, month, yy = ds[:2], ds[2:4], ds[4:]
                year = "19" + yy
                date_tokens.add("20" + yy)
            for x in [day, month, year, ds]:
                if x:
                    date_tokens.add(x)
            if day and month and year:
                date_tokens.update({day + month, month + day, day + month + year, year + month + day})
        tokens.extend(sorted(date_tokens))

        # Base combinations
        base: Set[str] = set()
        tokens = [t for t in tokens if t]
        tokens = list(dict.fromkeys(tokens))  # unique, keep order

        for r in range(1, min(MAX_COMBO_TOKENS, len(tokens)) + 1):
            for combo in itertools.permutations(tokens, r):
                for joined in _with_separators(list(combo)):
                    base.add(joined)

        # Expand with case and leet variants
        expanded: Set[str] = set()
        for w in base:
            variants = {w}
            if ADD_CASE_VARIANTS:
                variants = set().union(*(_case_variants(x) for x in variants))
            if ADD_LEET:
                variants = set().union(*(_leet_variants(x) for x in variants))
            expanded.update(variants)

        # Numeric tails
        if ADD_NUM_TAILS:
            tails = [str(i) for i in range(0, 100)]
            try:
                now_year = datetime.now().year
            except Exception:
                now_year = 2025
            tails += [str(y) for y in range(now_year - 10, now_year + 1)]
            expanded = _add_numeric_tails(expanded, tails)

        # Filter & save
        final_words = _unique_len_filtered(expanded)

        output_path = Path(OUTPUT_FILE)
        with open(output_path, "w", encoding="utf-8") as f:
            for w in sorted(final_words):
                f.write(w + "\n")

        self._console.print()
        self._console.print(Panel.fit(
            _Text(f"Generated {len(final_words)} words", style=THEME["ok"]),
            border_style=THEME["panel_border"],
            box=_HEAVY,
        ))

        stats = Table.grid(padding=(0, 1))
        stats.add_column(style=THEME["muted"], justify="right")
        stats.add_column()
        stats.add_row("Output:", str(output_path.resolve()))
        stats.add_row("Case:", "on" if ADD_CASE_VARIANTS else "off")
        stats.add_row("Leet:", "on" if ADD_LEET else "off")
        stats.add_row("Separators:", "on" if ADD_SEPARATORS else "off")
        stats.add_row("Num tails:", "on" if ADD_NUM_TAILS else "off")
        self._console.print(stats)
        self._console.print(Rule(style=THEME["muted"]))
        self._console.print(
            _Text("Use responsibly (lawful/ethical purposes only).", style=THEME["warn"])
        )
        self._console.print()

        self.prompt("Press Enter to continue...")

    async def cmd_passgen_config(self, *args) -> None:
        """Show current Passgen configuration."""
        self._console.print("\n[bold cyan]Passgen Configuration[/bold cyan]\n")

        config_table = Table(show_header=False, box=None)
        config_table.add_column("Setting", style="bold cyan", width=24)
        config_table.add_column("Value", style="white")
        config_table.add_row("MAX_COMBO_TOKENS", str(MAX_COMBO_TOKENS))
        config_table.add_row("ADD_LEET", str(ADD_LEET))
        config_table.add_row("ADD_CASE_VARIANTS", str(ADD_CASE_VARIANTS))
        config_table.add_row("ADD_SEPARATORS", str(ADD_SEPARATORS))
        config_table.add_row("ADD_NUM_TAILS", str(ADD_NUM_TAILS))
        config_table.add_row("MIN_LEN", str(MIN_LEN))
        config_table.add_row("MAX_LEN", str(MAX_LEN))
        config_table.add_row("OUTPUT_FILE", OUTPUT_FILE)
        self._console.print(config_table)
        self._console.print("\n[dim]Edit pegasus/modules/passgen/module.py to change settings.[/dim]")
        self.prompt("Press Enter to continue...")
