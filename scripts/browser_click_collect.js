const childProcess = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith("--")) continue;
    const key = item.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) args[key] = true;
    else {
      args[key] = next;
      i += 1;
    }
  }
  return args;
}

function findChrome() {
  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    path.join(os.homedir(), "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe"),
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ];
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) throw new Error("Chrome or Edge executable was not found.");
  return found;
}

function httpJson(url) {
  return new Promise((resolve, reject) => {
    http
      .get(url, (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () => {
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(error);
          }
        });
      })
      .on("error", reject);
  });
}

function postJson(url, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const parsed = new URL(url);
    const request = http.request(
      {
        hostname: parsed.hostname,
        port: parsed.port,
        path: parsed.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (response) => {
        let data = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          data += chunk;
        });
        response.on("end", () => {
          try {
            resolve(JSON.parse(data || "{}"));
          } catch (error) {
            reject(error);
          }
        });
      },
    );
    request.on("error", reject);
    request.write(body);
    request.end();
  });
}

async function waitForTarget(port) {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    try {
      const targets = await httpJson(`http://127.0.0.1:${port}/json/list`);
      const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
      if (page) return page;
    } catch {
      // Chrome is still starting.
    }
    await sleep(300);
  }
  throw new Error("Timed out waiting for Chrome debug target.");
}

function cdpCall(ws, method, params = {}) {
  const id = ++cdpCall.lastId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      ws.removeEventListener("message", onMessage);
      reject(new Error(`CDP call timed out: ${method}`));
    }, 20_000);
    function onMessage(event) {
      const payload = JSON.parse(event.data);
      if (payload.id !== id) return;
      clearTimeout(timeout);
      ws.removeEventListener("message", onMessage);
      if (payload.error) reject(new Error(payload.error.message));
      else resolve(payload.result);
    }
    ws.addEventListener("message", onMessage);
  });
}
cdpCall.lastId = 0;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForProcessExit(processHandle) {
  if (!processHandle || processHandle.exitCode !== null) return;
  await new Promise((resolve) => {
    processHandle.once("exit", resolve);
    setTimeout(resolve, 2500);
  });
}

async function evaluate(ws, expression) {
  const result = await cdpCall(ws, "Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  return result.result.value;
}

async function captureScreenshot(ws) {
  try {
    const result = await cdpCall(ws, "Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    return `data:image/png;base64,${result.data}`;
  } catch {
    return "";
  }
}

async function capturePage(ws) {
  return await evaluate(
    ws,
    `(() => {
      const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
      const links = Array.from(document.querySelectorAll("a[href]")).slice(0, 160).map((a) => ({
        text: clean(a.innerText || a.getAttribute("aria-label") || a.href).slice(0, 220),
        href: a.href
      })).filter((item) => item.text && item.href);
      const cards = Array.from(document.querySelectorAll("[data-e2e], article, section, div")).slice(0, 500)
        .map((node) => clean(node.innerText).slice(0, 500))
        .filter((text) => /(sold|price|shop|product|rating|review|views|likes|gmv|销量|售出|价格|商品|店铺)/i.test(text))
        .slice(0, 40);
      const tables = Array.from(document.querySelectorAll("table")).slice(0, 20).map((table) =>
        Array.from(table.querySelectorAll("tr")).slice(0, 90).map((row) =>
          Array.from(row.querySelectorAll("th,td")).slice(0, 18).map((cell) => clean(cell.innerText).slice(0, 220))
        ).filter((row) => row.some(Boolean))
      ).filter((rows) => rows.length > 1);
      const text = clean(document.body ? document.body.innerText : "");
      const metric_lines = text.split(/(?<=[.!?])\\s+|\\n+/).filter((line) => /(sold|price|shop|product|rating|review|views|likes|gmv|销量|售出|价格|商品|店铺)/i.test(line)).slice(0, 80);
      return { title: document.title || "", url: location.href, text: text.slice(0, 12000), links, cards, tables, metric_lines };
    })()`,
  );
}

async function performKeywordSearch(ws, keyword) {
  const cleanKeyword = String(keyword || "").trim();
  if (!cleanKeyword) return { searched: false, reason: "missing keyword" };
  const result = await evaluate(
    ws,
    `((keyword) => {
      const visible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 20 && rect.height > 12 && style.visibility !== "hidden" && style.display !== "none";
      };
      const scoreInput = (el) => {
        const hay = [
          el.getAttribute("placeholder"),
          el.getAttribute("aria-label"),
          el.getAttribute("name"),
          el.getAttribute("type"),
          el.id,
          el.className,
        ].join(" ").toLowerCase();
        let score = visible(el) ? 20 : -100;
        if (hay.includes("search") || hay.includes("keyword") || hay.includes("搜索") || hay.includes("关键词")) score += 50;
        if (hay.includes("product") || hay.includes("goods") || hay.includes("商品")) score += 30;
        if (hay.includes("email") || hay.includes("password") || hay.includes("phone")) score -= 80;
        return score;
      };
      const inputs = Array.from(document.querySelectorAll("input, textarea"))
        .filter((el) => !el.disabled && !el.readOnly)
        .map((el) => ({ el, score: scoreInput(el) }))
        .sort((a, b) => b.score - a.score);
      const picked = inputs.find((item) => item.score > 0);
      if (!picked) return { searched: false, reason: "no visible search input" };
      const input = picked.el;
      input.focus();
      input.value = keyword;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      const form = input.closest("form");
      if (form) form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      return {
        searched: true,
        placeholder: input.getAttribute("placeholder") || "",
        type: input.getAttribute("type") || "",
        url: location.href
      };
    })(${JSON.stringify(cleanKeyword)})`,
  );
  if (!result || !result.searched) return result || { searched: false, reason: "search script returned empty" };
  try {
    await cdpCall(ws, "Input.dispatchKeyEvent", { type: "keyDown", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, key: "Enter", code: "Enter" });
    await cdpCall(ws, "Input.dispatchKeyEvent", { type: "keyUp", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, key: "Enter", code: "Enter" });
  } catch {
    // Some pages react to input/change alone.
  }
  await sleep(5000);
  return result;
}

function hasVerification(snapshot) {
  const haystack = `${snapshot.title}\n${snapshot.text}`.toLowerCase();
  return [
    "captcha",
    "security check",
    "verify to continue",
    "verify it is you",
    "verify it's you",
    "verify you are human",
    "drag the puzzle",
    "puzzle piece",
    "drag the puzzle piece",
    "verification",
    "slider",
    "安全验证",
    "验证码",
    "滑块",
    "请完成验证",
    "sign in",
    "log in",
    "login",
    "登录",
    "登入",
  ].find((signal) => haystack.includes(signal));
}
async function candidateLinks(ws, maxClicks) {
  const links = await evaluate(
    ws,
    `(() => {
      const clean = (value) => String(value || "").replace(/\\s+/g, " ").trim();
      const candidates = Array.from(document.querySelectorAll("a[href]")).map((a) => {
        const text = clean(a.innerText || a.getAttribute("aria-label") || a.href);
        return { text: text.slice(0, 220), href: a.href };
      }).filter((item) => {
        const hay = (item.text + " " + item.href).toLowerCase();
        return item.href && /(video|creator|author|influencer|e-commerce|market|shop-marketing|search|live|ads?|advertis|达人|创作者|素材|选爆品|找达人|看竞店|查直播|商品|店铺|直播|广告|product|shop|item|detail|goods|tiktok\.com\/@|\/video\/|\/t\/|\/view\/product|\/product\/|shop\.tiktok\.com|visit shop|view shop|buy now|add to cart|sold|price|views|likes)/i.test(hay);
      });
      const seen = new Set();
      const unique = candidates.filter((item) => {
        const key = item.href.split("#")[0];
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      const score = (item) => {
        const hay = (item.text + " " + item.href).toLowerCase();
        let value = 0;
        if (hay.includes("shop.tiktok.com")) value += 80;
        if (/tiktok\\.com\\/.+\\/video\\//.test(hay) || hay.includes("tiktok.com/@")) value += 50;
        if (/(product|goods|item|detail|商品|详情|打开|查看)/i.test(hay)) value += 35;
        if (/(creator|达人|author|influencer|shop|店铺)/i.test(hay)) value += 20;
        if (/(login|sign in|register|privacy|terms|help|about)/i.test(hay)) value -= 40;
        return value;
      };
      return unique.sort((a, b) => score(b) - score(a)).slice(0, 20);
    })()`,
  );
  return (links || []).slice(0, maxClicks);
}

async function navigate(ws, url) {
  await cdpCall(ws, "Page.navigate", { url });
  await sleep(5500);
}

async function waitForVerificationClear(ws, waitSeconds) {
  const deadline = Date.now() + Number(waitSeconds || 0) * 1000;
  while (Date.now() < deadline) {
    await sleep(5000);
    const snapshot = await capturePage(ws);
    const barrier = hasVerification(snapshot);
    if (!barrier) return { cleared: true, snapshot };
  }
  return { cleared: false, snapshot: await capturePage(ws) };
}

async function captureToServer(server, source, snapshot, screenshot, notes) {
  const barrier = hasVerification(snapshot);
  if (barrier) {
    return { ok: false, manual_gate: true, reason: `Verification detected before saving: ${barrier}` };
  }
  const payload = {
    record_type: source.recordType,
    url: snapshot.url,
    title: snapshot.title,
    source_platform: source.sourcePlatform,
    notes,
    fields: {
      marketplace: source.marketplace,
      source_platform: source.sourcePlatform,
      ranking_type: "AI Browser Buyer-Side Click Collection",
      collection_goal: source.collectionGoal,
      data_category: source.dataCategory,
      keyword: source.searchKeyword,
      search_keyword: source.searchKeyword,
      product_target_id: source.productTargetId,
      product_target_name: source.productTargetName,
      product_family: source.productFamily,
      reference_image: source.referenceImage,
      selection_bridge: source.selectionBridge,
      bridge_provider: source.bridgeProvider,
      follow_tiktok_product_links: source.followTiktokProductLinks,
      monitoring_scope: source.productTargetId ? "product_target" : "buyer_side_collection",
      page_title: snapshot.title,
      page_url: snapshot.url,
      visible_growth_signal: notes,
      browser_operator: true,
    },
    page_snapshot: snapshot,
    screenshot_data_url: screenshot,
    browser: "ai_browser_operator",
  };
  return await postJson(`${server.replace(/\/$/, "")}/api/capture`, payload);
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const root = args.root || process.cwd();
  const source = {
    sourceId: args["source-id"] || "browser-source",
    url: args.url,
    recordType: args["record-type"] || "platform_ranking_signal",
    sourcePlatform: args["source-platform"] || "browser",
    marketplace: args.marketplace || args["source-platform"] || "browser",
    collectionGoal: args["collection-goal"] || "browser_collection",
    dataCategory: args["data-category"] || "",
    searchKeyword: args["search-keyword"] || "",
    productTargetId: args["product-target-id"] || "",
    productTargetName: args["product-target-name"] || "",
    productFamily: args["product-family"] || "",
    referenceImage: args["reference-image"] || "",
    bridgeProvider: args["bridge-provider"] || "",
    selectionBridge: args["selection-bridge"] === "true",
    followTiktokProductLinks: args["follow-tiktok-product-links"] === "true",
  };
  const maxClicks = Number(args["max-clicks"] || 3);
  const server = args.server || "http://127.0.0.1:8765";
  const initialWaitMs = Number(args["initial-wait-seconds"] || 14) * 1000;
  const verificationWaitSeconds = Number(args["verification-wait-seconds"] || 0);
  const keepOpenAfterRun = args["keep-open-after-run"] === true || args["keep-open-after-run"] === "true";
  const keepOpenOnGate = args["keep-open-on-gate"] !== false && args["keep-open-on-gate"] !== "false";
  let keepBrowserOpen = keepOpenAfterRun;
  if (!source.url) throw new Error("Missing --url.");

  const chromePath = findChrome();
  const port = 9440 + Math.floor(Math.random() * 400);
  const profileDir = path.join(root, "data", "browser_operator_profiles", source.sourceId);
  fs.mkdirSync(profileDir, { recursive: true });
  const chromeArgs = [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    "--no-first-run",
    "--no-default-browser-check",
    source.url,
  ];
  if (args.incognito) chromeArgs.splice(chromeArgs.length - 1, 0, "--incognito");
  if (args.headless) chromeArgs.unshift("--headless=new", "--disable-gpu");
  const chrome = childProcess.spawn(chromePath, chromeArgs, { stdio: "ignore", detached: keepOpenAfterRun || keepOpenOnGate });

  let ws;
  let capturedPages = 0;
  let clicked = 0;
  try {
    const target = await waitForTarget(port);
    ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve, { once: true });
      ws.addEventListener("error", reject, { once: true });
    });
    await cdpCall(ws, "Runtime.enable");
    await cdpCall(ws, "Page.enable");
    await sleep(initialWaitMs);

    let firstSnapshot = await capturePage(ws);
    const barrier = hasVerification(firstSnapshot);
    if (barrier) {
      keepBrowserOpen = keepBrowserOpen || keepOpenOnGate;
      if (verificationWaitSeconds > 0) {
        const waited = await waitForVerificationClear(ws, verificationWaitSeconds);
        if (waited.cleared) {
          firstSnapshot = waited.snapshot;
        } else {
          console.log(JSON.stringify({
            status: "manual_gate",
            reason: `Verification or login detected: ${barrier}. Browser window was kept open for human verification; run again after passing it.`,
            captured_pages: 0,
            clicked: 0,
            browser_kept_open: keepBrowserOpen,
            waited_seconds: verificationWaitSeconds
          }, null, 2));
          return;
        }
      } else {
      console.log(JSON.stringify({
        status: "manual_gate",
        reason: `Verification or login detected: ${barrier}. Browser window was kept open for human verification; run again after passing it.`,
        captured_pages: 0,
        clicked: 0,
        browser_kept_open: keepBrowserOpen
      }, null, 2));
      return;
      }
    }
    let searchResult = { searched: false, reason: "not requested" };
    if (source.searchKeyword) {
      searchResult = await performKeywordSearch(ws, source.searchKeyword);
      firstSnapshot = await capturePage(ws);
    }
    const firstNotes = source.searchKeyword
      ? `AI browser opened the selection/search entry, searched keyword "${source.searchKeyword}" (${searchResult.searched ? "searched" : searchResult.reason}), and captured visible ranking/product signals.`
      : "AI browser opened TikTok buyer-side video/shop entry and captured visible competitor signals.";
    const firstSave = await captureToServer(server, source, firstSnapshot, await captureScreenshot(ws), firstNotes);
    if (firstSave && firstSave.manual_gate) {
      keepBrowserOpen = args["keep-open-on-gate"] !== false && args["keep-open-on-gate"] !== "false";
      console.log(JSON.stringify({
        status: "manual_gate",
        reason: firstSave.reason,
        captured_pages: 0,
        clicked: 0,
        browser_kept_open: keepBrowserOpen
      }, null, 2));
      return;
    }
    capturedPages += 1;

    const candidates = await candidateLinks(ws, maxClicks);
    for (const link of candidates) {
      await navigate(ws, link.href);
      const snapshot = await capturePage(ws);
      const linkBarrier = hasVerification(snapshot);
      if (linkBarrier) {
        keepBrowserOpen = keepBrowserOpen || keepOpenOnGate;
        if (verificationWaitSeconds > 0) {
          const waited = await waitForVerificationClear(ws, verificationWaitSeconds);
          if (waited.cleared) {
            const waitedSave = await captureToServer(server, source, waited.snapshot, await captureScreenshot(ws), `AI browser clicked buyer-side video/shop/product link for competitor discovery: ${link.text}`);
            if (waitedSave && waitedSave.manual_gate) {
              console.log(JSON.stringify({
                status: "manual_gate",
                reason: waitedSave.reason,
                captured_pages: capturedPages,
                clicked,
                browser_kept_open: keepBrowserOpen
              }, null, 2));
              return;
            }
            clicked += 1;
            capturedPages += 1;
            await sleep(1200);
            continue;
          }
        }
        console.log(JSON.stringify({
          status: "manual_gate",
          reason: `Verification or login detected after clicking: ${linkBarrier}. Browser window was kept open for human verification; run again after passing it.`,
          captured_pages: capturedPages,
          clicked,
          browser_kept_open: keepBrowserOpen
        }, null, 2));
        return;
      }
      const linkSave = await captureToServer(server, source, snapshot, await captureScreenshot(ws), `AI browser clicked buyer-side video/shop/product link for competitor discovery: ${link.text}`);
      if (linkSave && linkSave.manual_gate) {
        keepBrowserOpen = keepBrowserOpen || keepOpenOnGate;
        console.log(JSON.stringify({
          status: "manual_gate",
          reason: linkSave.reason,
          captured_pages: capturedPages,
          clicked,
          browser_kept_open: keepBrowserOpen
        }, null, 2));
        return;
      }
      clicked += 1;
      capturedPages += 1;
      await sleep(1200);
    }
    console.log(JSON.stringify({ status: "completed", captured_pages: capturedPages, clicked }, null, 2));
  } finally {
    if (ws) ws.close();
    if (!keepBrowserOpen) {
      chrome.kill();
      await waitForProcessExit(chrome);
    } else {
      chrome.unref();
    }
  }
}

run().catch((error) => {
  console.log(JSON.stringify({ status: "failed", reason: String(error && error.message ? error.message : error), captured_pages: 0, clicked: 0 }, null, 2));
  process.exitCode = 1;
});
