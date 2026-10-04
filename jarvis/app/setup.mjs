// えふぃぞー の自動セットアップ（L2）
// ElevenLabs の APIキーを使って、会話AIのエージェントを作る（2回目以降は上書き更新）。
// - APIキーは、この実行の間だけ使い、どこにも保存しない
// - できた Agent ID は config.json に保存する
//
//   node setup.mjs            … 対話しながら作る／更新する
//   node setup.mjs --dry-run  … APIを呼ばずに、送る内容だけ表示する
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import { loadConfig, saveConfig } from "./server.mjs";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const API = "https://api.elevenlabs.io";
const DRY = process.argv.includes("--dry-run");

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((r) => rl.question(q, (a) => r(a.trim())));

// 入力した文字を画面に出さずに読む（APIキー用）
function askSecret(q) {
  return new Promise((resolve) => {
    const out = rl.output;
    const orig = rl._writeToOutput;
    rl._writeToOutput = (s) => {
      if (s.includes(q)) out.write(s);
      else if (s === "\r\n" || s === "\n") out.write(s);
      else out.write("*");
    };
    rl.question(q, (a) => {
      rl._writeToOutput = orig;
      out.write("\n");
      resolve(a.trim());
    });
  });
}

async function api(key, method, p, body) {
  const res = await fetch(API + p, {
    method,
    headers: { "xi-api-key": key, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    const err = new Error(`${method} ${p} → ${res.status} ${detail}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function explain(e) {
  if (e.status === 401) return "APIキーが違うか、権限が足りません。キーを作り直すか、権限に「Agents（書き込み）」「Voices（読み取り）」を付けてください。";
  if (e.status === 404) return "見つかりませんでした。Agent ID が消されている可能性があります。もう一度実行して「新しく作る」を選んでください。";
  if (e.status === 422) return "送った設定の形が、ElevenLabs 側の仕様と合いませんでした。下のエラーをそのまま Claude に貼って「直して」と頼んでください。";
  if (e.status === 429) return "回数制限か、利用枠の上限です。少し待つか、利用状況のページを確認してください。";
  return "ネットにつながっているか確認してください。直らなければ、下のエラーをそのまま Claude に貼ってください。";
}

async function previewVoice(url) {
  if (!url) return console.log("  この声には試聴データがありません。");
  const file = path.join(os.tmpdir(), "efizo-preview.mp3");
  const res = await fetch(url);
  await writeFile(file, Buffer.from(await res.arrayBuffer()));
  const player = process.platform === "darwin" ? ["afplay", [file]] : null;
  if (!player) return console.log("  試聴ファイル: " + file);
  await new Promise((r) => execFile(player[0], player[1], () => r()));
}

async function chooseVoice(key) {
  const data = await api(key, "GET", "/v2/voices?page_size=100");
  const voices = data.voices || [];
  if (!voices.length) return null;
  // 日本語の確認が取れている声を先に並べる
  const ja = (v) => (v.verified_languages || []).some((l) => l.language === "ja");
  voices.sort((a, b) => Number(ja(b)) - Number(ja(a)));
  console.log("\n使える声（★は日本語の確認が取れている声）:");
  voices.forEach((v, i) => {
    const l = v.labels || {};
    const tags = [l.gender, l.age, l.accent, l.description || l.descriptive].filter(Boolean).join(" / ");
    console.log(`  ${String(i + 1).padStart(2)}. ${ja(v) ? "★" : "  "}${v.name}${tags ? "（" + tags + "）" : ""}`);
  });
  console.log("\n番号を入れると決定。「p 番号」で試聴（例: p 3）。Enter だけなら 1 番。");
  for (;;) {
    const a = await ask("声を選ぶ > ");
    const m = a.match(/^p\s*(\d+)$/i);
    if (m) {
      const v = voices[Number(m[1]) - 1];
      if (v) await previewVoice(v.preview_url);
      continue;
    }
    const n = a === "" ? 1 : Number(a);
    if (voices[n - 1]) return voices[n - 1];
    console.log("  番号が見つかりません。");
  }
}

async function main() {
  const agentDef = JSON.parse(await readFile(path.join(DIR, "agent/agent.json"), "utf8"));
  const prompt = await readFile(path.join(DIR, "agent/system_prompt.txt"), "utf8");
  const config = await loadConfig();

  console.log("=== えふぃぞー 自動セットアップ ===");
  console.log("ElevenLabs に、会話AI「" + agentDef.name + "」を作ります。");

  const body = (voiceId) => ({
    name: agentDef.name,
    conversation_config: {
      agent: {
        first_message: agentDef.first_message,
        language: agentDef.language,
        prompt: { prompt },
      },
      tts: { model_id: agentDef.tts_model, ...(voiceId ? { voice_id: voiceId } : {}) },
    },
  });

  if (DRY) {
    console.log("\n[dry-run] 送る内容:\n" + JSON.stringify(body("VOICE_ID"), null, 2));
    return;
  }

  let key = process.env.ELEVENLABS_API_KEY || "";
  if (!key) {
    console.log("\nAPIキーを貼り付けて Enter（画面には * で表示されます。保存はしません）");
    key = await askSecret("APIキー > ");
  }
  if (!key) throw Object.assign(new Error("APIキーが空です"), { status: 401 });

  const voice = await chooseVoice(key);
  if (voice) console.log(`\n声: ${voice.name}`);

  let agentId = config.agentId;
  if (agentId) {
    const a = await ask(`\nすでに Agent ID（${agentId.slice(0, 10)}…）があります。上書き更新しますか？ [Y/n/new] > `);
    if (/^n(o)?$/i.test(a)) return console.log("何もせず終了します。");
    if (/^new$/i.test(a)) agentId = "";
  }

  if (agentId) {
    await api(key, "PATCH", `/v1/convai/agents/${encodeURIComponent(agentId)}`, body(voice?.voice_id));
    console.log("\nエージェントを更新しました。");
  } else {
    const res = await api(key, "POST", "/v1/convai/agents/create", body(voice?.voice_id));
    agentId = res.agent_id;
    console.log("\nエージェントを作りました。");
  }

  // 作ったものを読み直して、日本語になっているか確かめる
  const check = await api(key, "GET", `/v1/convai/agents/${encodeURIComponent(agentId)}`);
  const lang = check?.conversation_config?.agent?.language;
  console.log(`確認: 言語=${lang}　最初のひとこと=「${check?.conversation_config?.agent?.first_message}」`);
  if (lang !== "ja") console.log("⚠ 言語が日本語になっていません。ElevenLabs の画面で Agent language を Japanese にしてください。");

  await saveConfig({ agentId });
  console.log("Agent ID を config.json に保存しました。APIキーは保存していません。");
}

main()
  .catch((e) => {
    console.error("\nセットアップできませんでした。");
    console.error("→ " + explain(e));
    console.error("エラー: " + e.message);
    process.exitCode = 1;
  })
  .finally(() => rl.close());
