/**
 * OAuth login URLs for platforms reachable by the broker.
 * Each opens in the browser and returns to the app authenticated
 * via /api/oauth/callback/<provider>.
 */

export interface AuthProvider {
  id: string;
  label: string;
  authorizeUrl: string;
  callback: string;
  note: string;
  oauthFlow: string;
}

export const AUTH_PROVIDERS: AuthProvider[] = [
  {
    id: "signal",
    label: "Signal",
    authorizeUrl: "/api/oauth/signal/link",
    callback: "sgnl:// (QR device link)",
    note: "Not OAuth — QR device link relayed via adb",
    oauthFlow: "QR device link",
  },
  {
    id: "telegram",
    label: "Telegram",
    authorizeUrl: "https://oauth.telegram.org/auth",
    callback: "/api/oauth/callback/telegram",
    note: "Login Widget — signed hash verified with bot token",
    oauthFlow: "Login Widget",
  },
  {
    id: "whatsapp",
    label: "WhatsApp",
    authorizeUrl: "/api/oauth/login/whatsapp",
    callback: "/api/oauth/callback/whatsapp",
    note: "Business API OAuth",
    oauthFlow: "OAuth2 + PKCE",
  },
  {
    id: "discord",
    label: "Discord",
    authorizeUrl: "/api/oauth/login/discord",
    callback: "/api/oauth/callback/discord",
    note: "Standard OAuth2 + PKCE",
    oauthFlow: "OAuth2 + PKCE",
  },
  {
    id: "messenger",
    label: "Messenger",
    authorizeUrl: "/api/oauth/login/messenger",
    callback: "/api/oauth/callback/messenger",
    note: "Facebook Login — needs app review for pages_messaging",
    oauthFlow: "Facebook Login",
  },
];

export function openLogin(provider: string): void {
  const p = AUTH_PROVIDERS.find((x) => x.id === provider);
  if (!p) return;
  if (p.id === "signal") {
    // Signal links via sgnl:// QR capture — handled by the app shell
    window.open(p.authorizeUrl, "_blank");
    return;
  }
  if (p.authorizeUrl.startsWith("http")) {
    window.open(p.authorizeUrl, "_blank");
  } else {
    window.open(p.authorizeUrl, "_blank");
  }
}
