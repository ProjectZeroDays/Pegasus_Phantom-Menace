"""Capability taxonomy. Modules require caps; transports provide them.

A transport may not advertise a cap it fails in the conformance suite — `provides`
is derived from passes, never declared by hand.

Member NAME is the Python handle (SHELL). Member VALUE is the wire name ("shell").
Manifests and transport `provides` both use the value. scripts/capreg.py parses
this file with ast, so a reformat cannot change the parsed set.
"""
from __future__ import annotations

from enum import Enum


class Cap(str, Enum):
    SHELL = "shell"
    FILE_GET = "file.get"
    FILE_PUT = "file.put"
    FILE_LIST = "file.list"
    PKG_LIST = "pkg.list"
    PKG_INSTALL = "pkg.install"
    PROC_LIST = "proc.list"
    UI_INJECT = "ui.inject"
    SCREEN = "screen.capture"
    CAMERA = "camera"
    MIC = "mic"
    SMS = "comms.sms"
    CALLS = "comms.calls"
    CONTACTS = "comms.contacts"
    LOCATION = "pos.location"
    WIFI = "radio.wifi"
    BT = "radio.bt"
    NFC = "radio.nfc"
    SDR = "radio.sdr"
    CREDS_STORE = "creds.store"
    KEYSTORE = "creds.keystore"
    DPAPI = "creds.dpapi"
    SHADOW = "creds.shadow"
    SAM = "creds.sam"
    LSASS = "creds.lsass"
    REGISTRY = "os.registry"
    SYSTEMD = "os.systemd"
    LAUNCHD = "os.launchd"
    CRON = "os.cron"
    MQTT = "proto.mqtt"
    COAP = "proto.coap"
    TR069 = "proto.tr069"
    SNMP = "proto.snmp"
    MODBUS = "proto.modbus"
    DNP3 = "proto.dnp3"
    S7 = "proto.s7"
    RTSP = "proto.rtsp"
    ONVIF = "proto.onvif"
    MAVLINK = "proto.mavlink"
    CAN = "vehicle.can"
    OBD = "vehicle.obd"
    SMB = "net.smb"
    WMI = "net.wmi"
    RDP = "net.rdp"
    SSH = "net.ssh"
    LDAP = "net.ldap"
    ADB = "net.adb"
    IDEVICE = "net.idevice"
    AGENT = "agent.rpc"
    PIVOT = "net.pivot"


READ_CAPS = frozenset({
    Cap.FILE_GET, Cap.FILE_LIST, Cap.PROC_LIST, Cap.PKG_LIST, Cap.SMS,
    Cap.CALLS, Cap.CONTACTS, Cap.LOCATION, Cap.WIFI, Cap.SCREEN,
})

WRITE_CAPS = frozenset({
    Cap.FILE_PUT, Cap.PKG_INSTALL, Cap.UI_INJECT, Cap.CREDS_STORE, Cap.CAMERA,
    Cap.MIC, Cap.KEYSTORE, Cap.DPAPI, Cap.SAM, Cap.LSASS, Cap.SHADOW,
})

DESTRUCTIVE_CAPS = frozenset({
    Cap.MODBUS, Cap.SNMP, Cap.CAN, Cap.OBD, Cap.MAVLINK, Cap.ONVIF,
})

ROLE_CAPS = {
    "analyst": READ_CAPS,
    "operator": READ_CAPS | WRITE_CAPS,
    "supervisor": READ_CAPS | WRITE_CAPS | DESTRUCTIVE_CAPS,
    "administrator": frozenset(Cap),
}
