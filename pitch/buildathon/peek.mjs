// Screenshot pages as a demo account: node buildathon/peek.mjs <who> <out.png> <url> [more urls...]
import { context, DESKTOP, launch, login, settle, BASE, sleep } from "../shoot/lib.mjs";
const [who, out, ...urls] = process.argv.slice(2);
const b = await launch();
const auth = await login(`demo.focs.${who}@example.com`);
const ctx = await context(b, { auth, device: { ...DESKTOP, scale: 1 } });
const p = await ctx.newPage();
let i = 0;
for (const u of urls) {
  await p.goto(BASE + u, { waitUntil: "domcontentloaded" }); await settle(p, 1500); await sleep(800);
  await p.screenshot({ path: out.replace(".png", `-${i++}.png`), fullPage: false });
}
await b.close();
