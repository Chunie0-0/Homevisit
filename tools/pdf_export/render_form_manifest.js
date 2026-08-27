const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");

(async () => {
  const root = path.resolve(__dirname, "../..");
  const browser = await puppeteer.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: "new",
    args: ["--no-sandbox", "--disable-gpu"],
  });
  const page = await browser.newPage();
  // A4 CSS viewport at 96 dpi. PDF generation below uses zero margins.
  await page.setViewport({ width: 794, height: 1123, deviceScaleFactor: 1 });
  await page.goto(`file://${path.join(root, "homevisit_form_v1.html")}`, { waitUntil: "networkidle0" });
  await page.emulateMediaType("print");
  await page.evaluate(async () => { if (document.fonts) await document.fonts.ready; });

  const manifest = await page.evaluate(() => {
    const all = [...document.querySelectorAll("[data-k]")]
      .filter(el => !el.closest("template"));
    const counts = Object.create(null);
    return all.map((el, index) => {
      const key = el.dataset.k;
      counts[key] = (counts[key] || 0) + 1;
      const suffix = counts[key] > 1 ? `__${counts[key]}` : "";
      const r = el.getBoundingClientRect();
      const label = el.closest(".ck");
      const target = label || el;
      const tr = target.getBoundingClientRect();
      return {
        field: el.type === "radio"
          ? `${key.replace(/[^A-Za-z0-9_]+/g, "_")}_radio`
          : `hv_${index + 1}_${key.replace(/[^A-Za-z0-9_]+/g, "_")}${suffix}`, 
        key,
        type: el.type || el.tagName.toLowerCase(),
        value: el.value || "",
        checked: !!el.checked,
        name: el.name || "",
        rect: { x: r.x, y: r.y, width: r.width, height: r.height },
        labelRect: { x: tr.x, y: tr.y, width: tr.width, height: tr.height },
      };
    });
  });

  const outDir = path.join(root, "dist");
  fs.mkdirSync(outDir, { recursive: true });
  await page.pdf({
    path: path.join(outDir, "homevisit_form_base.pdf"),
    format: "A4",
    printBackground: true,
    preferCSSPageSize: false,
    margin: { top: "0", right: "0", bottom: "0", left: "0" },
  });
  fs.writeFileSync(path.join(outDir, "homevisit_form_manifest.json"), JSON.stringify({
    cssPageWidth: 794,
    cssPageHeight: 1123,
    fields: manifest,
  }, null, 2));
  console.log(JSON.stringify({ fields: manifest.length, output: outDir }));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
