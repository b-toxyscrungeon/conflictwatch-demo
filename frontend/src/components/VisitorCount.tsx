import { useEffect, useState } from "react";

// All-time unique-visitor counter for the static demo, backed by GoatCounter
// (https://www.goatcounter.com). GoatCounter counts unique visitors without
// storing IP addresses. Enabled only when VITE_GOATCOUNTER (the site code, e.g.
// "conflictwatch" for conflictwatch.goatcounter.com) is set at build time, and
// "Allow adding visitor counts on your website" is on in GoatCounter's settings.
const CODE = import.meta.env.VITE_GOATCOUNTER;
const ENDPOINT = CODE ? `https://${CODE}.goatcounter.com` : null;

let scriptAdded = false;

/** Records this visit once per page load. Hash routes all count as the site root. */
function recordVisit() {
  if (!ENDPOINT || scriptAdded) return;
  scriptAdded = true;
  const s = document.createElement("script");
  s.async = true;
  s.src = "https://gc.zgo.at/count.js";
  s.dataset.goatcounter = `${ENDPOINT}/count`;
  document.head.appendChild(s);
}

export function VisitorCount() {
  const [count, setCount] = useState<string | null>(null);

  useEffect(() => {
    if (!ENDPOINT) return;
    recordVisit();
    const path = encodeURIComponent(window.location.pathname);
    fetch(`${ENDPOINT}/counter/${path}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { count?: string } | null) => setCount(j?.count ?? null))
      .catch(() => setCount(null));
  }, []);

  if (!count) return null;
  return (
    <div className="stats asof" title="Unique visitors since launch (updates every few hours)">
      {count} visitor{count === "1" ? "" : "s"}
    </div>
  );
}
