// えふぃぞー 専用画面のサーバー。Node.js 標準の http だけで動く。
// 127.0.0.1:4321 でだけ待ち受けるので、同じPCのブラウザ以外からは開けない。
import http from "node:http";
import { readFile, writeFile, copyFile, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HOST = "127.0.0.1";
const PORT = 4321;
const DIR = path.dirname(fileURLToPath(import.meta.url));
const CONFIG = path.join(DIR, "config.json");
const CONFIG_EXAMPLE = path.join(DIR, "config.example.json");
const LIB = path.join(DIR, "node_modules/@elevenlabs/client/dist/lib.iife.js");

const STATIC = {
  "/": ["public/index.html", "text/html; charset=utf-8"],
  "/app.js": ["public/app.js", "text/javascript; charset=utf-8"],
  "/style.css": ["public/style.css", "text/css; charset=utf-8"],
};

export async function loadConfig() {
  try {
    await access(CONFIG);
  } catch {
    await copyFile(CONFIG_EXAMPLE, CONFIG);
  }
  return JSON.parse(await readFile(CONFIG, "utf8"));
}

export async function saveConfig(patch) {
  const cur = await loadConfig();
  const next = { ...cur };
  if ("agentId" in patch) {
    const id = String(patch.agentId).trim();
    if (id && !/^[A-Za-z0-9_-]{8,128}$/.test(id)) throw new Error("Agent ID の形が正しくありません");
    next.agentId = id;
  }
  if ("wakeWords" in patch) {
    const words = (Array.isArray(patch.wakeWords) ? patch.wakeWords : [])
      .map((w) => String(w).trim())
      .filter(Boolean)
      .slice(0, 30);
    if (!words.length) throw new Error("呼びかけの言葉を1つ以上入れてください");
    next.wakeWords = words;
  }
  await writeFile(CONFIG, JSON.stringify(next, null, 2) + "\n");
  return next;
}

function send(res, status, type, body) {
  res.writeHead(status, { "Content-Type": type, "Cache-Control": "no-store" });
  res.end(body);
}

const json = (res, status, obj) => send(res, status, "application/json; charset=utf-8", JSON.stringify(obj));

async function readBody(req) {
  let size = 0;
  const chunks = [];
  for await (const c of req) {
    size += c.length;
    if (size > 64 * 1024) throw new Error("too large");
    chunks.push(c);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  try {
    if (req.method === "GET" && STATIC[url.pathname]) {
      const [file, type] = STATIC[url.pathname];
      return send(res, 200, type, await readFile(path.join(DIR, file)));
    }
    if (req.method === "GET" && url.pathname === "/lib/elevenlabs.js") {
      return send(res, 200, "text/javascript; charset=utf-8", await readFile(LIB));
    }
    if (url.pathname === "/api/config") {
      if (req.method === "GET") return json(res, 200, await loadConfig());
      if (req.method === "POST") {
        // 他のサイトから書き換えられないよう、同じ画面からの送信だけ受け付ける
        const origin = req.headers.origin;
        if (origin && origin !== `http://${HOST}:${PORT}`) return json(res, 403, { error: "forbidden" });
        try {
          return json(res, 200, await saveConfig(await readBody(req)));
        } catch (e) {
          return json(res, 400, { error: e.message });
        }
      }
    }
    if (url.pathname === "/favicon.ico") return send(res, 204, "image/x-icon", "");
    if (url.pathname === "/api/health") return json(res, 200, { ok: true });
    send(res, 404, "text/plain; charset=utf-8", "not found");
  } catch (e) {
    console.error(e);
    send(res, 500, "text/plain; charset=utf-8", "server error: " + e.message);
  }
});

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await loadConfig();
  server.on("error", (e) => {
    if (e.code === "EADDRINUSE") {
      console.log(`すでに http://${HOST}:${PORT} で動いています。`);
      process.exit(3);
    }
    throw e;
  });
  server.listen(PORT, HOST, () => {
    console.log(`えふぃぞー の画面: http://${HOST}:${PORT}`);
    console.log("このウィンドウを閉じると、サーバーが止まります。");
  });
}
