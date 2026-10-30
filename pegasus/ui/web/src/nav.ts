import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  Boxes,
  Camera,
  ClipboardList,
  Command,
  Cpu,
  Crosshair,
  Database,
  FileText,
  Gauge,
  Globe,
  HardDrive,
  Key,
  KeyRound,
  Layers,
  ListChecks,
  Lock,
  MapPin,
  MessageSquare,
  Monitor,
  Network,
  Phone,
  Puzzle,
  Radar,
  Radio,
  Rocket,
  Search,
  Server,
  Settings,
  Shield,
  ShieldAlert,
  Smartphone,
  Sparkles,
  Terminal,
  Users,
  Wifi,
  Wrench,
  Zap,
} from "lucide-react";
import type { ComponentType } from "react";

export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<{ size?: number | string; className?: string }>;
  badge?: string;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: "command",
    label: "Command",
    items: [
      { path: "/", label: "Mission Control", icon: Gauge },
      { path: "/devices", label: "Devices", icon: Smartphone },
      { path: "/monitoring", label: "Monitoring", icon: Activity },
    ],
  },
  {
    id: "access",
    label: "Access & Exploitation",
    items: [
      { path: "/access", label: "Access Workflow", icon: Crosshair },
      { path: "/workflows", label: "Workflow Engine", icon: Rocket },
      { path: "/zero-click", label: "Zero-Click", icon: Zap },
      { path: "/delivery", label: "Delivery", icon: Radio },
      { path: "/post-exploit", label: "Post-Exploitation", icon: Layers },
      { path: "/capabilities", label: "Capability Parity", icon: Shield },
      { path: "/cve", label: "CVE Scanner", icon: ShieldAlert },
    ],
  },
  {
    id: "device-data",
    label: "Device Data",
    items: [
      { path: "/locations", label: "Locations", icon: MapPin },
      { path: "/geofences", label: "Geofences", icon: Radar },
      { path: "/calls", label: "Call Logs", icon: Phone },
      { path: "/contacts", label: "Contacts", icon: Users },
      { path: "/messages", label: "Messages", icon: MessageSquare },
      { path: "/browser", label: "Browser", icon: Globe },
      { path: "/apps", label: "Applications", icon: Boxes },
      { path: "/media", label: "Photos & Video", icon: Camera },
      { path: "/wifi", label: "Wi-Fi Networks", icon: Wifi },
      { path: "/keylog", label: "Keystrokes", icon: Key },
      { path: "/activity", label: "Activity Timeline", icon: BarChart3 },
      { path: "/keywords", label: "Keywords", icon: Search },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    items: [
      { path: "/payloads", label: "Payloads", icon: Rocket },
      { path: "/wordlists", label: "Wordlists", icon: KeyRound },
      { path: "/sessions", label: "Sessions", icon: Terminal },
      { path: "/campaigns", label: "Campaigns", icon: ClipboardList },
      { path: "/reports", label: "Reports", icon: FileText },
    ],
  },
  {
    id: "network",
    label: "Network & Tools",
    items: [
      { path: "/network", label: "Network Scanner", icon: Network },
      { path: "/tools", label: "Toolbox", icon: Wrench },
      { path: "/skills", label: "Skills Catalog", icon: Sparkles },
    ],
  },
  {
    id: "system",
    label: "System",
    items: [
      { path: "/plugins", label: "Plugins", icon: Puzzle },
      { path: "/commands", label: "Command Center", icon: Command },
      { path: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export const ALL_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

/** Skills catalog — mirrors the agent skill packs shipped with the repository. */
export interface SkillEntry {
  id: string;
  name: string;
  group: string;
  description: string;
  commands: string[];
}

export const SKILL_CATALOG: SkillEntry[] = [
  {
    id: "android",
    name: "AndroidExploitAgent",
    group: "Mobile",
    description: "Android device exploitation: ADB, fastboot, FRP, rooting, payload delivery.",
    commands: ["adb-devices", "wireless-adb", "frp-bypass"],
  },
  {
    id: "ios",
    name: "IOSExploitAgent",
    group: "Mobile",
    description: "iOS device exploitation and PWA delivery paths.",
    commands: ["create-ipa"],
  },
  {
    id: "api",
    name: "APISnifferAgent",
    group: "Traffic",
    description: "API traffic interception and analysis with MITM hooks.",
    commands: ["tshark", "wireshark", "exploit"],
  },
  {
    id: "auto",
    name: "AutomobileExploitAgent",
    group: "Hardware",
    description: "Automotive CAN bus exploitation and ECU interrogation.",
    commands: ["netscan"],
  },
  {
    id: "bluetooth",
    name: "BluetoothExploitAgent",
    group: "Wireless",
    description: "Bluetooth attack surface discovery and exploitation.",
    commands: ["btscan", "netscan"],
  },
  {
    id: "bruteforce",
    name: "BruteForceAgent",
    group: "Credentials",
    description: "GPU-accelerated brute force and password cracking.",
    commands: ["brute-force", "crack-passwords", "passgen"],
  },
  {
    id: "cookie",
    name: "CookieHarvesterAgent",
    group: "Traffic",
    description: "Cookie theft and session hijacking workflows.",
    commands: ["dump-credentials", "exploit"],
  },
  {
    id: "deserialization",
    name: "DeserializationAgent",
    group: "Web",
    description: "Deserialization vulnerability exploitation chains.",
    commands: ["create-exploit"],
  },
  {
    id: "exploitation",
    name: "ExploitationAgent",
    group: "Core",
    description: "General exploitation framework and orchestration.",
    commands: ["exploit", "post-exploitation"],
  },
  {
    id: "fileparse",
    name: "FileParseExploitAgent",
    group: "Core",
    description: "File parsing vulnerability exploitation.",
    commands: ["generate-payload"],
  },
  {
    id: "iot",
    name: "IOTExploitAgent",
    group: "Hardware",
    description: "IoT device exploitation and firmware inspection.",
    commands: ["netscan", "exploit"],
  },
  {
    id: "linux",
    name: "LinuxExploitAgent",
    group: "Host",
    description: "Linux privilege escalation and exploitation.",
    commands: ["exploit", "harden-device"],
  },
  {
    id: "media",
    name: "MediaExploitAgent",
    group: "Core",
    description: "Media file exploitation and parser fuzzing.",
    commands: ["generate-payload"],
  },
  {
    id: "memory",
    name: "MemoryCorruptionAgent",
    group: "Core",
    description: "Memory corruption exploitation primitives.",
    commands: ["create-exploit"],
  },
  {
    id: "messaging",
    name: "MessagingRCEAgent",
    group: "Messaging",
    description: "Messaging protocol RCE exploitation (SMS/WhatsApp/Telegram).",
    commands: ["exploit", "btscan"],
  },
  {
    id: "nfc",
    name: "NFCExploitAgent",
    group: "Wireless",
    description: "NFC/RFID exploitation and tag emulation.",
    commands: ["netscan"],
  },
  {
    id: "osx",
    name: "OSXExploitAgent",
    group: "Host",
    description: "macOS exploitation and persistence.",
    commands: ["create-dmg", "exploit"],
  },
  {
    id: "payload",
    name: "PayloadEngineAgent",
    group: "Core",
    description: "Payload generation and obfuscation.",
    commands: ["generate-payload", "payload-mutate"],
  },
  {
    id: "scanner",
    name: "SecurityScannerAgent",
    group: "Assessment",
    description: "Security vulnerability scanning across targets.",
    commands: ["audit-security", "nmap-scan"],
  },
  {
    id: "ssrf",
    name: "SSRFExploitAgent",
    group: "Web",
    description: "Server-side request forgery exploitation.",
    commands: ["exploit"],
  },
  {
    id: "vuln",
    name: "VulnScannerAgent",
    group: "Assessment",
    description: "CVE vulnerability scanning with fingerprint correlation.",
    commands: ["cve-scan", "cve-list", "audit-security"],
  },
  {
    id: "windows",
    name: "WindowsExploitAgent",
    group: "Host",
    description: "Windows zero-click RCE exploitation.",
    commands: ["create-exe", "exploit"],
  },
  {
    id: "phantom",
    name: "PhantomWorkflowAgent",
    group: "Core",
    description: "Autonomous full-lifecycle access and post-exploitation orchestration.",
    commands: ["access-autonomous", "access-workflow-run", "post-exploitation"],
  },
];
