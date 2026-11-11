/* Batch 2 圈选台前端。
 *
 * 设计要点（第二版）：
 *   1) 编辑区**预载机器草稿**。第一版 `ROWS = []`，逼着人把整页文本重新点一遍，
 *      结果 148 行里 59 行没数值也被签了 CONFIRMED —— 这是设计错误，已改。
 *      现在人的动作是「删掉垃圾行 + 校对留下的 3~5 行」，而不是从零点选。
 *   2) 点选文本行仍然保留，作为「草稿里漏了某个参数」时的补充手段，追加到末尾。
 *   3) 导出前会拦：状态是 CONFIRMED 但 min/typ/max 全空的行不许悄悄混进去。
 */
const DRAFT = __DRAFT__;
const THRESH = __THRESH__;   // 由生成器注入，与 Python 侧的 THRESH 同源

// 导出文件名按批次注入。Batch 2 老生成器不注入 window.B3_EXPORT_NAME，
// 这里退回原来的默认名，保证它的行为一字不变；Batch 3 生成器按 --out-prefix
// 注入，例如 Batch3_B2_ANNOTATED.csv，避免六件草稿都顶着 Batch2 的名字。
const EXPORT_NAME = window.B3_EXPORT_NAME || "Batch2_ANNOTATED";

const FIELDS = ["sample_no", "file_name", "evidence_page", "table_title", "symbol",
  "parameter_name", "min_value", "typ_value", "max_value", "unit", "condition",
  "row_status", "notes", "reviewer", "confidence_score"];

const STATUS = [
  "DRAFT_AWAITING_HUMAN_CONFIRM",
  "CONFIRMED",
  "UNRESOLVED: 表格排版混乱，无法定位列",
  "EXCLUDED: 文档内无标准参数表",
  "EXCLUDED: 无 OCR 能力，无法建立 Gold"
];

// 单个单位记号。复合单位（V/µs、dBFS/Hz）由下面拼接，别一个个枚举，
// 漏掉一个就有整行单位空着（Slew rate 的 V/µs 就是这么丢的）。
const U1 = "(?:mV|µV|μV|kV|V|mA|µA|μA|nA|pA|A|kΩ|MΩ|Ω|ohm|°C|MHz|kHz|GHz|Hz"
         + "|ns|µs|μs|ms|ps|s|pF|nF|µF|μF|uF|mW|W|%|dBFS|dBFs|dB)";
const UNIT_RE = new RegExp("^" + U1 + "(?:\\/" + U1 + ")?$");

// U+2212（数学减号）以及各种破折号/全角连字符。PDF 里负号几乎都是 U+2212，
// 不先归一，`−65` 会被当成非数字串，`V_S− to V_S+` 里的分隔符也认不出来。
const MINUS_CHARS = /[\u2212\u2010\u2011\u2012\u2013\u2014\u2015\uFF0D]/g;
// 只认"像符号"的东西：全大写（VID / GND / IO）或带一段下标（V_IH）。
const SYM_RE = /^[A-Z\u0394][A-Z0-9]{0,11}$|^[A-Z\u0394][A-Z0-9]{0,3}_[A-Za-z0-9]{1,3}$/;

let ROWS = DRAFT.map(r => Object.assign({}, r, {_src: "draft"}));

function hasNum(r) {
  return ["min_value", "typ_value", "max_value"].some(k => (r[k] || "").trim() !== "");
}

function parseLine(raw) {
  // 点线引导符（`Package . . . . . 69`）里每个点都是独立 token，`\.{3,}` 匹配不到，
  // 必须按"两个以上带空白的点"整体吃掉，否则参数名会拖一串点。
  let s = raw.replace(MINUS_CHARS, "-").replace(/(?:\s*\.){2,}\s*/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  const toks = s.split(" ").filter(t => t && !/^to$/i.test(t));

  // 负号可能与数字被空格拆开（`- 65`），先合并，否则 min 丢掉符号变成 65。
  const merged = [];
  for (let i = 0; i < toks.length; i++) {
    const t = toks[i];
    if (/^[-+±]$/.test(t) && i + 1 < toks.length && /^\d/.test(toks[i + 1])) {
      merged.push(t + toks[i + 1]);
      i++;
      continue;
    }
    merged.push(t);
  }

  const nums = [], units = [], rest = [];
  for (const tk of merged) {
    if (tk === "-") continue;                 // 孤立的连字符只是分隔符
    if (/^\([^()]*\)$/.test(tk)) continue;    // `(320)` `(mV_p-p)` 是备选值/备注
    const m = tk.match(/^([±+\-]?\d+(?:\.\d+)?)([A-Za-zµμΩ°%\/]*)$/);
    if (m) {
      nums.push(m[1]);
      if (m[2]) units.push(m[2]);
      continue;
    }
    if (UNIT_RE.test(tk)) { units.push(tk); continue; }
    rest.push(tk);
  }

  // 首词像符号才摘出来。整行只剩符号时要允许 rest.length==1，
  // 否则 `VID ±2.5 V` 会把符号当成参数名；但整行没有数字时不动，那多半是标题行。
  let symbol = "";
  if (nums.length > 0 && rest.length >= 1 && rest[0].length <= 12 && SYM_RE.test(rest[0])) {
    symbol = rest.shift();
  }

  // 一个数都没解析出来的行不是参数行（表头、注释），参数名留空，
  // 原文进 notes，免得把 `. . . . .` 这类垃圾灌进参数名列。
  const name = nums.length ? rest.join(" ").replace(/[,;:]+$/, "").trim() : "";
  let unit = units.length ? units[units.length - 1] : "";
  unit = unit.replace(/\s*\([^)]*\)$/, "");
  let mn = "", typ = "", mx = "";
  if (nums.length === 1) mx = nums[0];
  else if (nums.length === 2) { mn = nums[0]; mx = nums[1]; }
  else if (nums.length >= 3) { mn = nums[0]; typ = nums[1]; mx = nums[2]; }
  return {symbol, name, min: mn, typ, max: mx, unit, nums: nums.length};
}

function msg(t) {
  document.getElementById("msg").textContent = t;
}

function addFromLine(li) {
  const box = li.closest(".pane");
  const p = parseLine(li.dataset.t);
  // 这些手册的表格里，数字和标签**不在同一条基线**（标签 y=382.7，数字 y=375.7），
  // 所以右侧必然出现"只有数字"的碎片行。点它只会造出一行没名字的垃圾，
  // 这种行进不了 Gold（无法判断它是什么参数），直接拦掉，提示去表里填。
  if (!p.name && !p.symbol) {
    msg("这行只有数字/单位，没有参数名 —— 请在下方对应行直接填数值，"
        + "或用「新增空行」自己写参数名。不要点它建行。");
    li.classList.add("dead");
    return;
  }
  ROWS.push({
    sample_no: box.dataset.sno,
    file_name: box.dataset.fn,
    evidence_page: box.dataset.page,
    table_title: box.dataset.title,
    symbol: p.symbol,
    parameter_name: p.name,
    min_value: p.min, typ_value: p.typ, max_value: p.max,
    unit: p.unit,
    condition: "",
    row_status: "DRAFT_AWAITING_HUMAN_CONFIRM",
    notes: "点选文本行生成，需与左图核对；原文：" + li.dataset.t.slice(0, 80),
    reviewer: "",
    confidence_score: "",
    _src: "click"
  });
  render();
  li.classList.add("picked");
}

function addBlank() {
  const s = document.getElementById("fsample").value;
  const sample = (s !== "*") ? s : (DRAFT[0] ? DRAFT[0].sample_no : "");
  const base = DRAFT.filter(r => r.sample_no === sample)[0] || {};
  ROWS.push({
    sample_no: sample,
    file_name: base.file_name || "",
    evidence_page: base.evidence_page || "",
    table_title: base.table_title || "",
    symbol: "", parameter_name: "",
    min_value: "", typ_value: "", max_value: "", unit: "", condition: "",
    row_status: "DRAFT_AWAITING_HUMAN_CONFIRM",
    notes: "人工新增",
    reviewer: "", confidence_score: "", _src: "manual"
  });
  render();
  msg("已在 " + sample + " 末尾新增一行，请填写参数名与数值");
}

function dropNoName() {
  const before = ROWS.length;
  ROWS = ROWS.filter(r => (r.parameter_name || "").trim() !== ""
                       || (r.symbol || "").trim() !== "");
  render();
  msg("已删除 " + (before - ROWS.length) + " 行既没有参数名也没有符号的行");
}

function visible() {
  const s = document.getElementById("fsample").value;
  const onlyNum = document.getElementById("fnum").checked;
  const onlyTodo = document.getElementById("ftodo").checked;
  const out = [];
  ROWS.forEach((r, i) => {
    if (s !== "*" && r.sample_no !== s) return;
    if (onlyNum && !hasNum(r)) return;
    if (onlyTodo && r.row_status === "CONFIRMED") return;
    out.push({r, i});
  });
  return out;
}

function cell(tr, opts) {
  const td = document.createElement("td");
  if (opts.text !== undefined) {
    td.textContent = opts.text;
    td.className = opts.cls || "";
  } else {
    const inp = document.createElement("input");
    inp.value = opts.value || "";
    inp.oninput = () => { opts.set(inp.value); refreshRowMeta(); };
    td.appendChild(inp);
    if (opts.num) td.className = "num";
  }
  tr.appendChild(td);
  return td;
}

function render() {
  const tb = document.getElementById("tbody");
  tb.innerHTML = "";
  const list = visible();
  for (const {r, i} of list) {
    const tr = document.createElement("tr");
    const cf = parseFloat(r.confidence_score || "");
    if (!isNaN(cf)) tr.className = cf >= THRESH ? "conf-ok" : "conf-low";
    if (!hasNum(r)) tr.classList.add("empty-row");
    if (r._src === "click") tr.classList.add("clicked");

    cell(tr, {text: r.sample_no || "", cls: "sn"});
    cell(tr, {text: r.evidence_page || "", cls: "num"});
    cell(tr, {value: r.symbol, set: v => r.symbol = v});
    cell(tr, {value: r.parameter_name, set: v => r.parameter_name = v});
    cell(tr, {value: r.min_value, set: v => r.min_value = v, num: true});
    cell(tr, {value: r.typ_value, set: v => r.typ_value = v, num: true});
    cell(tr, {value: r.max_value, set: v => r.max_value = v, num: true});
    cell(tr, {value: r.unit, set: v => r.unit = v});

    const tdS = document.createElement("td");
    const sel = document.createElement("select");
    for (const v of STATUS) {
      const o = document.createElement("option");
      o.value = v; o.textContent = v;
      if (v === r.row_status) o.selected = true;
      sel.appendChild(o);
    }
    sel.onchange = () => { r.row_status = sel.value; refreshRowMeta(); };
    tdS.appendChild(sel);
    tr.appendChild(tdS);

    cell(tr, {text: r.confidence_score || "-", cls: "num cf"});

    const tdD = document.createElement("td");
    const btn = document.createElement("button");
    btn.textContent = "删";
    btn.className = "mini";
    btn.onclick = () => { ROWS.splice(i, 1); render(); };
    tdD.appendChild(btn);
    tr.appendChild(tdD);

    tb.appendChild(tr);
  }
  document.getElementById("cnt").textContent =
    list.length + " / " + ROWS.length;
  refreshRowMeta();
}

function refreshRowMeta() {
  const all = ROWS.length;
  const num = ROWS.filter(hasNum).length;
  const conf = ROWS.filter(r => r.row_status === "CONFIRMED").length;
  const bad = ROWS.filter(r => r.row_status === "CONFIRMED" && !hasNum(r)).length;
  const noName = ROWS.filter(r => !(r.parameter_name || "").trim()
                                && !(r.symbol || "").trim()).length;
  const bySample = {};
  ROWS.forEach(r => {
    bySample[r.sample_no] = bySample[r.sample_no] || {n: 0, k: 0};
    bySample[r.sample_no].n++;
    if (hasNum(r)) bySample[r.sample_no].k++;
  });
  const parts = Object.keys(bySample).sort().map(s =>
    s + ":" + bySample[s].k + "/" + bySample[s].n);
  let t = "共 " + all + " 行：" + num + " 行有数值，" + conf + " 行已确认";
  if (bad) t += "，其中 " + bad + " 行确认了却没有数值（必须处理）";
  if (noName) t += "；" + noName + " 行既无参数名也无符号（进不了 Gold，建议删）";
  t += "　|　有数值/总数 " + parts.join("  ");
  const el = document.getElementById("stat");
  el.textContent = t;
  el.className = (bad || noName) ? "stat bad" : "stat";
}

function q(v) {
  v = (v === undefined || v === null) ? "" : String(v);
  return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}

function csvText() {
  const dropEmpty = document.getElementById("dropEmpty").checked;
  // 既没参数名也没符号的行进不了 Gold（读表的人无法判断它是什么参数），
  // 勾了"丢空行"就一起丢掉，别让它悄悄混进分母。
  const rows = ROWS.filter(r => !dropEmpty || (hasNum(r)
      && ((r.parameter_name || "").trim() || (r.symbol || "").trim())));
  const head = FIELDS.join(",");
  const lines = rows.map(r => FIELDS.map(f => q(r[f])).join(","));
  return {text: [head].concat(lines).join("\n"), n: rows.length};
}

function downloadCSV() {
  const {text, n} = csvText();
  // 前面加 U+FEFF（BOM）：Excel 看到 BOM 才按 UTF-8 解码，
  // 否则 ° µ − 会被当成无法映射的字符显示成 ?。
  const blob = new Blob(["\ufeff" + text], {type: "text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = EXPORT_NAME + ".csv";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  document.getElementById("msg").textContent =
    "已下载 " + EXPORT_NAME + ".csv（" + n + " 行，UTF-8 带 BOM，Excel 直接打开不乱码）";
}

function copyOut() {
  const ta = document.getElementById("out");
  ta.value = csvText().text;
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  document.getElementById("msg").textContent = ok
    ? "已复制到剪贴板，粘到 Excel 即可"
    : "复制失败：请手动 Ctrl+A 全选文本框再 Ctrl+C";
}

function cleanEmpty() {
  const s = document.getElementById("fsample").value;
  const before = ROWS.length;
  ROWS = ROWS.filter(r => (s !== "*" && r.sample_no !== s) || hasNum(r));
  render();
  document.getElementById("msg").textContent =
    "已删除 " + (before - ROWS.length) + " 行无 min/typ/max 的空行";
}

function resetDraft() {
  if (!confirm("放弃所有改动，恢复到机器草稿？")) return;
  ROWS = DRAFT.map(r => Object.assign({}, r, {_src: "draft"}));
  render();
  msg("已恢复机器草稿");
}

/* ---- CSV 回导：换新版本页面时把上次的进度接回来，不用重做 ---- */
function parseCSVText(text) {
  text = text.replace(/^\ufeff/, "");
  const rows = [];
  let row = [], cur = "", inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') { cur += '"'; i++; }
        else inQ = false;
      } else cur += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") { row.push(cur); cur = ""; }
    else if (c === "\n") { row.push(cur); rows.push(row); row = []; cur = ""; }
    else if (c === "\r") { /* 丢掉 */ }
    else cur += c;
  }
  if (cur !== "" || row.length) { row.push(cur); rows.push(row); }
  return rows;
}

function importCSV(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  const r = new FileReader();
  r.onload = () => {
    try {
      const table = parseCSVText(String(r.result));
      if (table.length < 2) throw new Error("文件里没有数据行");
      const head = table.shift().map(s => s.trim());
      if (head[0] !== "sample_no") {
        throw new Error("表头第一列不是 sample_no，可能不是这个页面导出的文件");
      }
      const objs = [];
      for (const a of table) {
        if (!a.length || !(a[0] || "").trim()) continue;
        const o = {};
        FIELDS.forEach(k => o[k] = "");
        head.forEach((h, i) => {
          if (FIELDS.indexOf(h) >= 0) o[h] = (a[i] || "").trim();
        });
        o._src = "import";
        objs.push(o);
      }
      if (!objs.length) throw new Error("解析出 0 行");
      ROWS = objs;
      fillSamples();
      document.getElementById("fsample").value = "*";
      render();
      msg("已导入 " + objs.length + " 行，可以接着改");
    } catch (e) {
      msg("导入失败：" + e.message);
    } finally {
      input.value = "";
    }
  };
  r.readAsText(f, "utf-8");
}

function fillSamples() {
  const sel = document.getElementById("fsample");
  const keep = sel.value;
  sel.innerHTML = "";
  const seen = [];
  ROWS.forEach(r => { if (seen.indexOf(r.sample_no) < 0) seen.push(r.sample_no); });
  ["*"].concat(seen.sort()).forEach(s => {
    const o = document.createElement("option");
    o.value = s;
    o.textContent = s === "*" ? "全部样本" : s;
    sel.appendChild(o);
  });
  if (seen.indexOf(keep) >= 0 || keep === "*") sel.value = keep;
}

document.addEventListener("click", (e) => {
  const li = e.target.closest("li.line");
  if (li && !li.classList.contains("dead")) addFromLine(li);
});

document.addEventListener("DOMContentLoaded", () => {
  fillSamples();
  document.getElementById("fsample").value = "*";
  ["fsample", "fnum", "ftodo"].forEach(id =>
    document.getElementById(id).addEventListener("change", render));
  document.getElementById("fimp").addEventListener("change", (e) => importCSV(e.target));
  render();
});
