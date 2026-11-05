/** Class-name join with last-wins conflict resolution. */

type ClassValue = string | number | null | false | undefined | Record<string, boolean> | ClassValue[];

const FAMILIES: [RegExp, string][] = [
  [/^-?(m|p)[trblxy]?-(?:\d|\[)/, "spacing"],
  [/^(w|h|min-w|min-h|max-w|max-h)-/, "size"],
  [/^(text|bg|border|ring|fill|stroke)-/, "color"],
  [/^text-(?:xs|sm|base|lg|xl|\d)/, "fontsize"],
  [/^font-/, "weight"],
  [/^(flex|grid|block|inline|hidden|table)(?:-|$)/, "display"],
  [/^(items|justify|self|content)-/, "align"],
  [/^(rounded|shadow|opacity|z|gap)-?/, "box"],
];

function flatten(value: ClassValue, out: string[]): void {
  if (!value && value !== 0) return;
  if (typeof value === "string" || typeof value === "number") {
    for (const token of String(value).split(/\s+/)) if (token) out.push(token);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) flatten(item, out);
    return;
  }
  for (const [key, on] of Object.entries(value)) if (on) flatten(key, out);
}

function familyOf(token: string): string | null {
  const bare = token.replace(/^[a-z]+:/, "");
  for (const [pattern, name] of FAMILIES) if (pattern.test(bare)) return `${token.split(":")[0] ?? ""}|${name}`;
  return null;
}

/** Join conditional class values, dropping utilities a later class overrides. */
export function cn(...inputs: ClassValue[]): string {
  const tokens: string[] = [];
  flatten(inputs, tokens);
  const seen = new Map<string, number>();
  const kept: string[] = [];
  for (const token of tokens) {
    const family = familyOf(token);
    if (!family) {
      kept.push(token);
      continue;
    }
    const previous = seen.get(family);
    if (previous !== undefined) kept[previous] = "";
    seen.set(family, kept.length);
    kept.push(token);
  }
  return kept.filter(Boolean).join(" ");
}

export default cn;
