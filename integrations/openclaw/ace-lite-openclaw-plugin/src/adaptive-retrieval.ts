export function shouldSkipRetrieval(prompt: string): boolean {
  const text = String(prompt || "").trim();
  if (!text) return true;
  if (text.startsWith("/")) return true;
  if (text.length < 8) return true;

  const lower = text.toLowerCase();
  const skipPrefixes = [
    "hi",
    "hello",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "good",
    "nice",
  ];
  if (skipPrefixes.some((p) => lower === p || lower.startsWith(`${p} `))) {
    return true;
  }

  return false;
}

