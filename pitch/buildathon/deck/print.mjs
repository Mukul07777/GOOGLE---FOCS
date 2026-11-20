// Prints deck.html to out/Focs-Buildathon-Deck.pdf (1920x1080 pages) and PNG previews of each slide.
//   node buildathon/deck/print.mjs [--png]
import path from "node:path";
import fs from "node:fs";
import { pathToFileURL, fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(here, "..", "..", "out");
fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch({ channel: "chrome" });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await p.goto(pathToFileURL(path.join(here, "deck.html")).href, { waitUntil: "networkidle" });
await p.evaluate(() => document.fonts.ready);
await p.pdf({ path: path.join(out, "Focs-Buildathon-Deck.pdf"), width: "1920px", height: "1080px", printBackground: true, preferCSSPageSize: true });
if (process.argv.includes("--png")) {
  const n = await p.locator("section.slide").count();
  for (let i = 0; i < n; i++) await p.locator("section.slide").nth(i).screenshot({ path: path.join(out, `deck-${String(i + 1).padStart(2, "0")}.png`) });
}
await b.close();
console.log("wrote", path.join(out, "Focs-Buildathon-Deck.pdf"));
