"""
Passgen module plugin entry point.
Wordlist generator based on user-provided info (name, surname, nickname, team, date).
"""
from pegasus.modules.passgen.module import PassgenModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="passgen",
    version="2.0.0",
    description="Wordlist generator - custom wordlists from name, surname, nickname, team, date with case/leet/separator/numeric variations",
    author="Hexec",
    category="credentials",
    tags=["wordlist", "password", "generator", "bruteforce", "credentials", "wordlist-generator"],
    requires=["rich"],
    requires_python=">=3.9",
    entry_point="main",
)


def create_plugin(context):
    return PassgenModule(context)


main = create_plugin
