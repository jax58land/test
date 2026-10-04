// えふぃぞー 専用画面
// 耳 = Chrome の音声認識（呼びかけの検知だけ）
// 頭と口 = ElevenLabs の会話AI（@elevenlabs/client）
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const IDLE_LIMIT_MS = 60_000;
  const CONNECT_TIMEOUT_MS = 20_000;
  const END_PHRASES = ["会話を終了", "えふぃぞー終了", "えふぃぞう終了"];
  const STATE_LABEL = {
    off: "待受オフ",
    waiting: "待受中",
    connecting: "接続中",
    listening: "聞いています",
    speaking: "話しています",
  };

  let config = { agentId: "", wakeWords: [] };
  let state = "off";
  let armed = false; // 待受をオンにしているか
  let recognition = null;
  let recognizing = false;
  let conversation = null;
  let idleTimer = null;
  let micGranted = null;
  let activeSeq = 0; // いま有効な接続の番号（古い接続からの知らせを無視するため）

  // ---------- 文字の正規化（呼びかけ判定用） ----------
  const SMALL = { "ァ": "ア", "ィ": "イ", "ゥ": "ウ", "ェ": "エ", "ォ": "オ", "ャ": "ヤ", "ュ": "ユ", "ョ": "ヨ" };
  function normalize(text) {
    return String(text)
      .normalize("NFKC")
      .toLowerCase()
      .replace(/[ぁ-ゖ]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0x60)) // ひらがな→カタカナ
      .replace(/[ァィゥェォャュョ]/g, (c) => SMALL[c])
      .replace(/[ー〜~\-\s、。，．,.!?！？「」『』・]/g, "");
  }
  const containsAny = (text, words) => {
    const t = normalize(text);
    return words.some((w) => {
      const n = normalize(w);
      return n && t.includes(n);
    });
  };

  // ---------- 画面 ----------
  function setState(next) {
    state = next;
    $("orb").dataset.state = next;
    $("state").textContent = STATE_LABEL[next];
    const inConv = ["connecting", "listening", "speaking"].includes(next);
    $("btnArm").textContent = armed ? "待受をオフ" : "待受をオン";
    $("btnArm").classList.toggle("on", armed);
    $("btnTalk").disabled = inConv;
    $("btnEnd").disabled = !inConv;
  }

  function addLog(who, text) {
    const log = $("log");
    if (log.querySelector(".muted")) log.innerHTML = "";
    const div = document.createElement("div");
    div.className = "msg";
    const time = new Date().toLocaleTimeString("ja-JP", { hour12: false });
    const label = { user: "おぬし", agent: "えふぃぞー", sys: "お知らせ" }[who];
    const head = document.createElement("div");
    head.className = "who " + who;
    head.textContent = `${label}　${time}`;
    const body = document.createElement("div");
    body.textContent = text;
    div.append(head, body);
    log.append(div);
    log.scrollTop = log.scrollHeight;
  }

  function showError(what, next) {
    const el = $("error");
    el.hidden = false;
    el.textContent = `${what}　次に確認すること：${next}`;
    addLog("sys", what);
  }
  const clearError = () => ($("error").hidden = true);

  function setCheck(id, ok, hint) {
    const li = $(id);
    const mark = li.querySelector(".mark");
    mark.textContent = ok === null ? "−" : ok ? "○" : "×";
    mark.className = "mark " + (ok === null ? "" : ok ? "ok" : "ng");
    li.querySelector("small").textContent = ok ? "" : hint || "";
  }

  function refreshChecks() {
    setCheck("chkAgent", !!config.agentId, "直し方：右の設定に Agent ID を貼って「保存」を押してください。");
    if (micGranted === null) setCheck("chkMic", null, "−（待受をオンにすると確認します）");
    else setCheck("chkMic", micGranted, "直し方：「待受をオン」を押して、出てきた確認で「許可」を押してください。");
    setCheck("chkSr", !!SpeechRecognition, "直し方：Google Chrome でこの画面を開いてください。");
  }

  async function checkMicPermission() {
    try {
      const st = await navigator.permissions.query({ name: "microphone" });
      micGranted = st.state === "granted" ? true : st.state === "denied" ? false : null;
      st.onchange = () => {
        micGranted = st.state === "granted" ? true : st.state === "denied" ? false : null;
        refreshChecks();
      };
    } catch {
      micGranted = null;
    }
    refreshChecks();
  }

  async function requestMic() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      micGranted = true;
      refreshChecks();
      return true;
    } catch (e) {
      micGranted = false;
      refreshChecks();
      showError("マイクが許可されていません。", "アドレスバー左のマークでマイクを「許可」にして、ページを読み込み直す。Macは システム設定→プライバシーとセキュリティ→マイク→Google Chrome をオン。");
      return false;
    }
  }

  // ---------- 耳：呼びかけの検知 ----------
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function createRecognition() {
    const r = new SpeechRecognition();
    r.lang = "ja-JP";
    r.continuous = true;
    r.interimResults = true;
    r.onstart = () => (recognizing = true);
    r.onresult = (ev) => {
      let text = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) text += ev.results[i][0].transcript;
      $("heard").textContent = "聞き取った言葉：" + text;
      if (state === "waiting" && containsAny(text, config.wakeWords)) {
        addLog("sys", `呼びかけを聞き取りました（${text}）。接続します。`);
        startConversation();
      }
    };
    r.onerror = (ev) => {
      if (ev.error === "not-allowed" || ev.error === "service-not-allowed") {
        armed = false;
        micGranted = false;
        refreshChecks();
        setState("off");
        showError("マイク（音声認識）が許可されていません。", "アドレスバー左のマークでマイクを「許可」にして、ページを読み込み直す。");
      } else if (ev.error === "network") {
        showError("音声認識がネットにつながりません。", "インターネットにつながっているか確認する。");
      }
      // no-speech / aborted は無音や停止なので何もしない
    };
    r.onend = () => {
      recognizing = false;
      // 無音で止まっても、待受中なら自動で再開する
      if (armed && state === "waiting") setTimeout(startRecognition, 250);
    };
    return r;
  }

  function startRecognition() {
    if (!SpeechRecognition || recognizing || !armed || state !== "waiting") return;
    recognition = recognition || createRecognition();
    try {
      recognition.start();
    } catch {
      /* すでに開始している */
    }
  }

  // 音声認識を止め、止まったのを確認する（最大1秒待つ）
  function stopRecognition() {
    return new Promise((resolve) => {
      if (!recognition || !recognizing) return resolve();
      const done = () => {
        clearTimeout(t);
        recognition.removeEventListener("end", done);
        resolve();
      };
      const t = setTimeout(done, 1000);
      recognition.addEventListener("end", done);
      try {
        recognition.stop();
      } catch {
        done();
      }
    });
  }

  // ---------- 頭と口：ElevenLabs との会話 ----------
  function touch() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      addLog("sys", "60秒間やりとりがなかったので、会話を終了します。");
      endConversation();
    }, IDLE_LIMIT_MS);
  }

  function callbacks(seq) {
    const live = () => seq === activeSeq;
    return {
      onConnect: () => {
        if (!live()) return;
        clearError();
        setState("listening");
        touch();
      },
      onMessage: ({ message, role, source }) => {
        if (!live()) return;
        const who = (role || (source === "ai" ? "agent" : "user")) === "agent" ? "agent" : "user";
        addLog(who, message);
        touch();
        if (who === "user" && containsAny(message, END_PHRASES)) endConversation();
      },
      onModeChange: ({ mode }) => {
        if (!live()) return;
        if (conversation) setState(mode === "speaking" ? "speaking" : "listening");
        touch();
      },
      onError: (message) => console.warn("ElevenLabs:", message),
      onDisconnect: () => {
        if (live() && state !== "connecting") afterConversation();
      },
    };
  }

  function withTimeout(promise, ms) {
    let timer;
    return Promise.race([
      promise,
      new Promise((_, reject) => (timer = setTimeout(() => reject(new Error("timeout")), ms))),
    ]).finally(() => clearTimeout(timer));
  }

  async function tryStart(connectionType) {
    const seq = ++activeSeq;
    const p = ElevenLabsClient.Conversation.startSession({
      agentId: config.agentId,
      connectionType,
      ...callbacks(seq),
    });
    try {
      return await withTimeout(p, CONNECT_TIMEOUT_MS);
    } catch (e) {
      // 時間切れのあとに遅れてつながった場合は、すぐ切る
      if (seq === activeSeq) activeSeq++;
      p.then((c) => c.endSession()).catch(() => {});
      throw e;
    }
  }

  async function startConversation() {
    if (conversation || state === "connecting") return;
    if (!config.agentId) {
      showError("Agent ID が入っていません。", "右の設定に Agent ID を貼って「保存」を押す。");
      return;
    }
    if (typeof ElevenLabsClient === "undefined") {
      showError("会話の部品（ElevenLabsの部品）が読み込めていません。", "黒いウィンドウを閉じて、start.command をもう一度ダブルクリックする。");
      return;
    }
    setState("connecting");
    await stopRecognition();
    try {
      try {
        conversation = await tryStart("webrtc");
      } catch (first) {
        console.warn("1回目の接続に失敗。websocket でやり直します。", first);
        addLog("sys", "つながりにくいので、別の方法でもう一度つなぎます。");
        conversation = await tryStart("websocket");
      }
    } catch (e) {
      conversation = null;
      showError("ElevenLabs に接続できませんでした。", "Agent ID が合っているか（前後に空白がないか）／今月の利用枠が残っているか／ネットにつながっているか。");
      afterConversation();
    }
  }

  async function endConversation() {
    clearTimeout(idleTimer);
    const c = conversation;
    if (!c) return afterConversation();
    try {
      await c.endSession();
    } catch {
      afterConversation();
    }
  }

  // 会話が終わったら、始める前の状態（待受中 or 待受オフ）に戻る
  function afterConversation() {
    clearTimeout(idleTimer);
    const had = !!conversation;
    conversation = null;
    activeSeq++;
    if (had) addLog("sys", "会話を終了しました。");
    setState(armed ? "waiting" : "off");
    if (armed) startRecognition();
  }

  // ---------- ボタン ----------
  $("btnArm").onclick = async () => {
    clearError();
    if (armed) {
      armed = false;
      await stopRecognition();
      if (!conversation) setState("off");
      else setState(state);
      return;
    }
    if (!SpeechRecognition) {
      showError("このブラウザでは音声認識が使えません。", "Google Chrome でこの画面を開く。呼びかけなしで話すなら「今すぐ話す」を使う。");
      return;
    }
    // 呼びかけた瞬間に許可の確認が出て止まらないよう、先に許可を取っておく
    if (!(await requestMic())) return;
    armed = true;
    if (!conversation) {
      setState("waiting");
      startRecognition();
    } else setState(state);
  };

  $("btnTalk").onclick = async () => {
    clearError();
    if (!(await requestMic())) return;
    startConversation();
  };

  $("btnEnd").onclick = () => endConversation();

  async function save(patch) {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    const data = await res.json();
    if (!res.ok) {
      $("saved").textContent = "保存できませんでした：" + data.error;
      return;
    }
    config = data;
    $("saved").textContent = "保存しました（" + new Date().toLocaleTimeString("ja-JP", { hour12: false }) + "）";
    fillForm();
    refreshChecks();
  }

  function fillForm() {
    $("agentId").value = config.agentId || "";
    $("wakeWords").value = (config.wakeWords || []).join("、");
  }

  $("saveAgent").onclick = () => save({ agentId: $("agentId").value.trim() });
  $("saveWake").onclick = () => save({ wakeWords: $("wakeWords").value.split(/[、,，]/) });

  // ---------- 起動 ----------
  (async () => {
    try {
      config = await (await fetch("/api/config")).json();
    } catch {
      showError("設定を読み込めませんでした。", "黒いウィンドウが開いたままか確認する。閉じていたら start.command をもう一度ダブルクリック。");
    }
    fillForm();
    setState("off"); // ページを開いただけでは、会話も待受も始めない
    await checkMicPermission();
  })();
})();
