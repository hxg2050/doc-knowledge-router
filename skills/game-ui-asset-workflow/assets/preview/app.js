/* No build step, external fonts, CDN, or runtime dependencies. */
"use strict";
const $ = id => document.getElementById(id);
const node = (tag, text, className) => {
  const e = document.createElement(tag);
  if (text != null) e.textContent = text;
  if (className) e.className = className;
  return e;
};
const link = (title, url, download = false) => {
  const e = node("a", title); e.href = url;
  if (download) e.download = "";
  else { e.target = "_blank"; e.rel = "noopener"; }
  return e;
};
const loadImage = url => new Promise((resolve, reject) => {
  if (!url) { resolve(null); return; }
  const image = new Image(); image.onload = () => resolve(image);
  image.onerror = () => reject(new Error(`图片读取失败：${url}`)); image.src = url;
});
const category = a => a.kind === "text" ? "text" : a.kind === "geometry" ? "geometry" : "art";
const names = {art: "美术", text: "文字", geometry: "简单几何"};

async function start() {
  const response = await fetch("data.json", {cache: "no-store"});
  if (!response.ok) throw new Error(`清单读取失败：HTTP ${response.status}`);
  const data = await response.json(), [width, height] = data.canvas;
  const assets = new Map(data.assets.map(a => [a.id, a]));
  const images = new Map();
  const reference = await loadImage(data.reference);
  await Promise.all(data.assets.filter(a => a.url).map(async a => images.set(a.id, await loadImage(a.url))));
  const visible = new Set(data.instances.map(i => i.id));
  const ordered = data.instances.slice().sort((a, b) => a.z - b.z);
  let highlighted = null;
  const phaseNames = {accepted: "严格验收通过", "review-needed": "严格验收待完成", "assets-needed": "素材待处理", "assets-ready": "素材结构检查通过"};
  $("phase").textContent = phaseNames[data.state.phase] || "阶段预览";
  if (data.state.phase === "accepted") $("phase").classList.add("accepted");
  const counts = data.state.counts;
  $("summary").textContent = `${width} × ${height} · 美术 ${counts.art} · 文字 ${counts.text} · 简单几何 ${counts.geometry} · ${data.instances.length} 个实例` +
    (data.state.review_current ? ` · 当前视觉评分 ${data.state.visual_score}/100` :
      data.state.strict_review === "not-requested" ? " · 快速预览，未进行严格视觉验收" : " · 严格视觉验收尚未通过");
  for (const problem of data.state.blockers) $("blocker-list").append(node("li", problem));
  for (const asset of data.assets.filter(a => !a.status.passed)) {
    $("blocker-list").append(node("li", `${asset.id}：${asset.status.errors.join("；")}`));
  }
  if (!$("blocker-list").childElementCount) $("blocker-list").append(node("li",
    data.state.review_current ? "当前严格验收无阻塞项" : "素材结构检查未发现阻塞项，视觉效果以实际查看为准"));

  const assembled = document.createElement("canvas"); assembled.width = width; assembled.height = height;
  const ac = assembled.getContext("2d"), canvas = $("canvas");
  function render() {
    ac.clearRect(0, 0, width, height);
    for (const item of ordered) if (visible.has(item.id) && images.has(item.asset)) ac.drawImage(images.get(item.asset), ...item.xy);
    const mode = $("mode").value, ratio = Number($("mix").value) / 100;
    canvas.width = mode === "side" ? width * 2 : width; canvas.height = height;
    const context = canvas.getContext("2d");
    const drawRef = x => { if (reference) context.drawImage(reference, x, 0, width, height); };
    if (mode === "reference") drawRef(0);
    else if (mode === "assembly") context.drawImage(assembled, 0, 0);
    else if (mode === "side") { drawRef(0); context.drawImage(assembled, width, 0); }
    else if (mode === "swipe") {
      context.drawImage(assembled, 0, 0); context.save(); context.beginPath();
      context.rect(0, 0, width * ratio, height); context.clip(); drawRef(0); context.restore();
      context.fillStyle = "#b74b36"; context.fillRect(Math.round(width * ratio), 0, Math.max(1, width / 800), height);
    } else if (mode === "overlay") {
      drawRef(0); context.globalAlpha = ratio; context.drawImage(assembled, 0, 0); context.globalAlpha = 1;
    } else {
      // Compare against white so transparent pixels have the same interpretation as the CLI.
      context.fillStyle = "white"; context.fillRect(0, 0, width, height); drawRef(0);
      const first = context.getImageData(0, 0, width, height);
      context.fillStyle = "white"; context.fillRect(0, 0, width, height); context.drawImage(assembled, 0, 0);
      const second = context.getImageData(0, 0, width, height);
      for (let i = 0; i < first.data.length; i += 4) {
        for (let c = 0; c < 3; c++) first.data[i + c] = Math.min(255, Math.abs(first.data[i + c] - second.data[i + c]) * 4);
        first.data[i + 3] = 255;
      }
      context.putImageData(first, 0, 0);
    }
    if (highlighted && mode !== "reference" && mode !== "difference") {
      const item = data.instances.find(i => i.id === highlighted), asset = assets.get(item.asset);
      context.strokeStyle = "#d13d25"; context.lineWidth = Math.max(1, width / 500); context.setLineDash([8, 5]);
      context.strokeRect(item.xy[0] + (mode === "side" ? width : 0), item.xy[1], ...asset.size);
    }
    $("mix-value").textContent = `${Math.round(ratio * 100)}%`;
    $("mix").disabled = !["swipe", "overlay"].includes(mode);
    const captions = {swipe: "左：效果原图 / 右：独立素材实时拼装", side: "左：效果原图 / 右：独立素材实时拼装", assembly: "独立 PNG 按坐标和层级实时拼装", reference: "固定的整体效果原图", overlay: "效果原图上叠加拼装结果，可调整透明度", difference: "RGB 像素差异放大 4 倍"};
    $("caption").textContent = captions[mode];
  }
  $("mode").addEventListener("change", render); $("mix").addEventListener("input", render);
  $("background").addEventListener("change", () => {
    $("stage").className = `stage ${$("background").value}`;
    $("asset-picture").className = `asset-picture ${$("background").value}`;
    document.querySelectorAll(".thumb").forEach(e => e.className = `thumb ${$("background").value}`);
  });
  function locate(item) {
    highlighted = item.id; $("mode").value = "assembly"; render();
    $("compare").scrollIntoView({behavior: "smooth"});
  }
  for (const item of ordered) {
    const row = node("label", null, "layer"), box = document.createElement("input");
    box.type = "checkbox"; box.checked = true; box.dataset.instance = item.id;
    box.addEventListener("change", () => { if (box.checked) visible.add(item.id); else visible.delete(item.id); highlighted = null; render(); });
    const locateButton = node("button", "定位"); locateButton.type = "button";
    locateButton.addEventListener("click", event => { event.preventDefault(); locate(item); });
    row.append(box, node("span", `${item.id} · z${item.z}`), locateButton); $("layers").append(row);
  }
  $("reset").addEventListener("click", () => { ordered.forEach(i => visible.add(i.id)); document.querySelectorAll(".layer input").forEach(e => e.checked = true); highlighted = null; render(); });

  const dialog = $("asset-dialog");
  $("close-dialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", e => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } });
  function showAsset(asset) {
    $("asset-title").textContent = asset.id; $("asset-picture").replaceChildren(); $("asset-links").replaceChildren();
    if (asset.url) { const img = new Image(); img.src = asset.url; img.alt = asset.id; $("asset-picture").append(img); $("asset-links").append(link("下载独立 PNG", asset.url, true)); }
    else $("asset-picture").append(node("span", "素材尚未生成"));
    $("asset-info").textContent = JSON.stringify({尺寸: asset.size, 类型: asset.kind, 获取方式: asset.strategy || "旧清单", Alpha: asset.alpha,
      生成轮次: asset.round, 实例: asset.instances, 检查: asset.status.alpha, 问题: asset.status.errors, 说明: asset.source_note}, null, 2);
    if (asset.alpha_preview) $("asset-links").append(link("深浅底检查图", asset.alpha_preview));
    for (const source of asset.sources) if (source.url) $("asset-links").append(link(source.path, source.url));
    for (const item of asset.instances) { const button = node("button", `定位 ${item.id}`); button.addEventListener("click", () => { dialog.close(); locate(item); }); $("asset-links").append(button); }
    dialog.showModal();
  }
  function renderAssets() {
    const query = $("search").value.trim().toLowerCase(), filter = $("filter").value;
    const filtered = data.assets.filter(a => `${a.id} ${a.kind} ${a.text || ""}`.toLowerCase().includes(query) &&
      (filter === "all" || (filter === "problem" ? !a.status.passed : category(a) === filter)));
    $("asset-grid").replaceChildren(); $("asset-count").textContent = `${filtered.length} / ${data.assets.length}`;
    $("empty").hidden = filtered.length > 0;
    for (const asset of filtered) {
      const card = node("button", null, "card"); card.type = "button"; card.dataset.asset = asset.id;
      const thumb = node("span", null, `thumb ${$("background").value}`), meta = node("span", null, "card-meta");
      if (asset.url) { const img = new Image(); img.src = asset.url; img.alt = asset.id; img.loading = "lazy"; thumb.append(img); }
      else thumb.append(node("span", "待生成"));
      meta.append(node("strong", asset.id), node("span", `${asset.size.join(" × ")} · ${names[category(asset)]}`));
      if (!asset.status.passed) meta.append(node("em", "待处理"));
      card.append(thumb, meta); card.addEventListener("click", () => showAsset(asset)); $("asset-grid").append(card);
    }
  }
  $("search").addEventListener("input", renderAssets); $("filter").addEventListener("change", renderAssets);
  for (const round of data.rounds) {
    const row = node("article", null, "round"); row.append(node("strong", round.id));
    if (round.image_url || round.raw_url) { const img = new Image(); img.src = round.image_url || round.raw_url; img.alt = `${round.id} 素材画布`; img.loading = "lazy"; row.append(img); }
    const links = node("div", null, "links");
    for (const [label, url] of [["原始生图", round.raw_url], ["标准化画布", round.image_url], ["提示词", round.prompt_url], ["尺寸标注", round.annotation_url], ["校正记录", round.recipe_url]]) if (url) links.append(link(label, url));
    row.append(links); $("round-list").append(row);
  }
  for (const item of data.evidence) $("evidence").append(link(item.path.replace("qa/", ""), item.url));
  renderAssets(); render();
  document.documentElement.dataset.ready = "true";
}
start().catch(error => { $("phase").textContent = "加载失败"; $("summary").textContent = `${error.message}。请用 HTTP 服务打开整个任务目录。`; $("summary").classList.add("error"); console.error(error); });
