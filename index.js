const express = require("express");
const puppeteer = require("puppeteer");
const fs = require("fs");

const app = express();
app.use(express.json());

const COOKIE_FILE = "cookies.json";
let browser;
let page;

// Cookie をファイルからロード
async function loadCookies(page) {
  if (fs.existsSync(COOKIE_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIE_FILE, "utf-8"));
    if (cookies.length > 0) {
      await page.setCookie(...cookies);
    }
  }
}

// Cookie を保存
async function saveCookies(page) {
  const cookies = await page.cookies();
  fs.writeFileSync(COOKIE_FILE, JSON.stringify(cookies, null, 2));
}

// Puppeteer 初期化
async function initBrowser() {
  browser = await puppeteer.launch({ headless: true });
  page = await browser.newPage();
  await loadCookies(page);
}
initBrowser();

// ========== エンドポイント ========== //

// HTMLを取得
app.post("/scrape", async (req, res) => {
  try {
    const { url } = req.body;
    if (!url) return res.status(400).send("URL is required");

    await page.goto(url, { waitUntil: "networkidle2" });
    await new Promise(r => setTimeout(r, 5000)); // 5秒待機

    const html = await page.content();
    await saveCookies(page);

    res.json({ html });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Cookie 一覧
app.get("/cookies", async (req, res) => {
  const cookies = await page.cookies();
  res.json(cookies);
});

// Cookie 追加・上書き
app.post("/cookies/add", async (req, res) => {
  try {
    const newCookies = req.body; // [{name, value, domain, path, ...}]
    await page.setCookie(...newCookies);
    await saveCookies(page);
    res.json({ message: "Cookies added/updated successfully" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Cookie 削除（指定した名前だけ）
app.delete("/cookies/delete", async (req, res) => {
  try {
    const { names } = req.body; // ["cookieName1", "cookieName2"]
    const cookies = await page.cookies();

    for (let name of names) {
      const target = cookies.find(c => c.name === name);
      if (target) {
        await page.deleteCookie({ name: target.name, domain: target.domain, path: target.path });
      }
    }

    await saveCookies(page);
    res.json({ message: "Cookies deleted successfully" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Cookie 全削除
app.delete("/cookies/clear", async (req, res) => {
  try {
    const cookies = await page.cookies();
    for (let c of cookies) {
      await page.deleteCookie({ name: c.name, domain: c.domain, path: c.path });
    }
    await saveCookies(page);
    res.json({ message: "All cookies cleared" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ========== サーバー起動 ========== //
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
