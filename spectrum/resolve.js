/** Map a Spectrum sender onto a Fareline rider. Pure, so tests need no credentials. */

export function loadMap(raw) {
  const text = (raw ?? "").trim();
  if (!text) return {};
  const data = JSON.parse(text);
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error(
      "SPECTRUM_SENDER_MAP must be a JSON object of sender id to rider name.",
    );
  }
  return data;
}

export function resolveRider(sender, map) {
  if (!sender || !map) return null;
  const candidates = [sender.id, sender.name, sender.displayName, sender.handle]
    .filter((value) => typeof value === "string" && value.trim());
  for (const candidate of candidates) {
    if (Object.prototype.hasOwnProperty.call(map, candidate)) {
      return map[candidate];
    }
    const match = Object.keys(map).find(
      (key) => key.toLowerCase() === candidate.toLowerCase(),
    );
    if (match) return map[match];
  }
  return null;
}
