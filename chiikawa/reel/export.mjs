// index.html を Chrome で1コマずつ描いて撮り、ffmpeg で MP4 にする。音も index.html の中で合成して重ねる。
//   node export.mjs                 … 映像と音を書き出して out/完成.mp4 を作る
//   node export.mjs --audio-only    … 映像は前回の out/映像のみ.mp4 を使い、音だけ作り直して重ねる
//   node export.mjs --stills 1.2,8,25 … 指定した秒のコマを out/frames/ に PNG で書き出す
// Chrome の場所は CHROME_PATH で指定できる（未指定なら Mac / Linux の定番の場所を探す）
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(DIR, "out");
const CANDIDATES = [
  process.env.CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);
const chrome = CANDIDATES.find((p) => existsSync(p));
if (!chrome) throw new Error("Chrome が見つかりません。CHROME_PATH で場所を指定してください。");

const stillsArg = process.argv.indexOf("--stills");
const stills = stillsArg > 0 ? process.argv[stillsArg + 1].split(",").map(Number) : null;
const audioOnly = process.argv.includes("--audio-only");

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: true,
  args: ["--no-sandbox", "--force-device-scale-factor=1", "--hide-scrollbars"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.join(DIR, "index.html")).href + "?export", { waitUntil: "load" });
await page.waitForFunction("window.__ready === true", { timeout: 60000 });
const { duration, fps } = await page.evaluate(() => ({ duration: window.DURATION, fps: window.FPS }));

// キャンバスの中身を PNG で取り出す（画面の拡大縮小に左右されない）
const grab = async (t) => {
  const b64 = await page.evaluate((t) => {
    window.renderAt(t);
    return document.getElementById("c").toDataURL("image/png").split(",")[1];
  }, t);
  return Buffer.from(b64, "base64");
};

if (stills) {
  mkdirSync(path.join(OUT, "frames"), { recursive: true });
  for (const t of stills) {
    const file = path.join(OUT, "frames", `t${t.toFixed(2)}.png`);
    writeFileSync(file, await grab(t));
    console.log("書き出し:", path.relative(DIR, file));
  }
  await browser.close();
  process.exit(0);
}

mkdirSync(OUT, { recursive: true });
const total = Math.round(duration * fps);
const video = path.join(OUT, "映像のみ.mp4");
const wav = path.join(OUT, "音.wav");
const mp4 = path.join(OUT, "完成.mp4");
const run = (args) => new Promise((res, rej) => {
  const p = spawn("ffmpeg", args, { stdio: ["pipe", "inherit", "inherit"] });
  p.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg " + c))));
  return p;
});

// 1. 音（音楽と効果音）を合成して WAV にする
const b64 = await page.evaluate(() => window.renderAudioWav());
writeFileSync(wav, Buffer.from(b64, "base64"));
console.log("音:", path.relative(DIR, wav));

// 2. 映像（音なし）
if (!audioOnly || !existsSync(video)) {
  const ff = spawn("ffmpeg", [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(fps), "-c:v", "png", "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
    "-r", String(fps), "-movflags", "+faststart", video,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((res, rej) => ff.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg " + c)))));
  const started = Date.now();
  for (let f = 0; f < total; f++) {
    const png = await grab(f / fps);
    if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once("drain", r));
    if (f % 60 === 0) process.stdout.write(`\r${f}/${total} コマ（${((Date.now() - started) / 1000).toFixed(0)}秒）`);
  }
  ff.stdin.end();
  await done;
  console.log();
}
await browser.close();

// 3. 映像と音を重ねる
await run(["-y", "-loglevel", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a",
  "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", mp4]);
console.log(`完成: ${path.relative(DIR, mp4)}（${total}コマ / ${duration.toFixed(2)}秒 / ${fps}fps / 音あり）`);
