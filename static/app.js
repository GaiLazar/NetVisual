/* NetVisual A+ — dashboard logic (vanilla JS, no deps) */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (x) => String(x ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------- global theme engine ---------- */
function applyTheme(name) {
  document.documentElement.setAttribute("data-theme", name);
  try { localStorage.setItem("netvisual_theme", name); } catch(e){}
  const sel = $("#themeSelect");
  if (sel && sel.value !== name) sel.value = name;
}
const savedTheme = (typeof localStorage !== "undefined" && localStorage.getItem("netvisual_theme")) || "cyber";
applyTheme(savedTheme);
$("#themeSelect")?.addEventListener("change", (e) => applyTheme(e.target.value));

/* ---------- collapsible cyber sidebar ---------- */
const cyberSidebar = $("#cyberSidebar");
const sidebarToggleBtn = $("#sidebarToggleBtn");
if (sidebarToggleBtn && cyberSidebar) {
  const isCol = localStorage.getItem("netvisual_sidebar_collapsed") === "1";
  if (isCol) {
    cyberSidebar.classList.add("collapsed");
    sidebarToggleBtn.textContent = "▶";
  }
  sidebarToggleBtn.addEventListener("click", () => {
    const collapsed = cyberSidebar.classList.toggle("collapsed");
    sidebarToggleBtn.textContent = collapsed ? "▶" : "◀";
    try { localStorage.setItem("netvisual_sidebar_collapsed", collapsed ? "1" : "0"); } catch(e){}
    setTimeout(() => { if (typeof geoMap !== "undefined" && geoMap) geoMap.invalidateSize(true); }, 260);
  });
}

/* ---------- mini floating hud widget ---------- */
function toggleHudMode(show) {
  const hud = $("#hudOverlay");
  if (!hud) return;
  hud.hidden = (show !== undefined) ? !show : !hud.hidden;
}
$("#hudModeBtn")?.addEventListener("click", () => toggleHudMode());
$("#closeHudBtn")?.addEventListener("click", () => toggleHudMode(false));

/* ---------- full-screen cyber noc wallboard mode ---------- */
function toggleNocMode(show) {
  const noc = $("#nocWallboard");
  if (!noc) return;
  const isHidden = (show !== undefined) ? !show : !noc.hidden;
  noc.hidden = isHidden;
  if (!isHidden) {
    updateNocWallboard();
    if (!window._nocInterval) window._nocInterval = setInterval(updateNocWallboard, 1500);
  } else {
    if (window._nocInterval) { clearInterval(window._nocInterval); window._nocInterval = null; }
  }
}
$("#nocModeBtn")?.addEventListener("click", () => toggleNocMode(true));
$("#closeNocBtn")?.addEventListener("click", () => toggleNocMode(false));
window.addEventListener("keydown", (e) => {
  if (e.key === "F11") {
    e.preventDefault();
    toggleNocMode();
  } else if (e.key === "Escape") {
    toggleNocMode(false);
  }
});

/* ---------- tabs ---------- */
$$(".tab").forEach(t => t.addEventListener("click", () => {
  $$(".tab").forEach(x => x.classList.remove("active"));
  $$(".panel").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  const p = $(`#panel-${t.dataset.tab}`);
  if (p) p.classList.add("active");
  if (t.dataset.tab === "topology") {
    requestAnimationFrame(() => loadTopology());
  } else if (t.dataset.tab === "geomap") {
    requestAnimationFrame(() => loadGeoMap());
  } else if (t.dataset.tab === "security") {
    loadSecurityAudit();
  } else if (t.dataset.tab === "wifi") {
    loadWifi();
  } else if (t.dataset.tab === "devices") {
    loadDevices();
  } else if (t.dataset.tab === "netprofiles") {
    loadNetProfiles();
  } else if (t.dataset.tab === "nettools") {
    loadDnsPresets();
    loadHostsStatus();
  } else if (t.dataset.tab === "trends") {
    loadTrends(trRange);
    loadStage1(trRange);
  }
}));

/* ---------- application exit / shutdown ---------- */
$("#shutdownBtn")?.addEventListener("click", async () => {
  if (!confirm("Are you sure you want to stop and completely exit NetVisual A+?\n\nThe server will shut down and release port 8730.")) return;
  try {
    await api("/api/server/shutdown");
  } catch (e) {}
  document.body.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;text-align:center;font-family:var(--sans);color:#94a3b8;background:var(--bg)">
      <div style="font-size:48px;margin-bottom:16px">🛑</div>
      <h1 style="color:#f87171;font-size:24px;margin-bottom:12px">NetVisual A+ Stopped</h1>
      <p style="font-size:15px;margin-bottom:18px;color:#cbd5e1">The local server has safely shut down and freed port 8730.</p>
      <p style="font-size:13px;color:#64748b">You may now close this browser tab.</p>
    </div>
  `;
});

/* ---------- status ---------- */
function setStatus(ok, label) {
  const el = $("#connStatus");
  el.className = "conn-status " + (ok ? "ok" : "bad");
  el.innerHTML = `<span class="dot"></span> ${label || (ok ? "live" : "offline")}`;
}

/* ---------- helpers ---------- */
async function api(path, opts) {
  const r = await fetch(path, opts);
  return r.json();
}
function badge(txt, cls) { return `<span class="badge ${cls}">${esc(txt)}</span>`; }
function fmtBps(n) {
  if (!n && n !== 0) return "0";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n >= 100 ? Math.round(n) : n.toFixed(1)} ${u[i]}`;
}
function fmtBytes(n) {
  if (!n) return "0";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n >= 100 ? Math.round(n) : n.toFixed(1)} ${u[i]}`;
}
function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
}

/* ---------- overview ---------- */
function setOverviewAlert(text, level = "ok") {
  const pill = $("#ovAlertPill"), txt = $("#ovAlertText");
  if (!pill || !txt) return;
  txt.textContent = text;
  pill.className = "ov-alert-pill " + level;
}

async function loadOverview() {
  const s = await api("/api/summary");
  $("#ovIp").textContent = s.self_ip || "—";
  $("#ovGw").textContent = s.gateway || "—";
  $("#ovSub").textContent = s.subnet || "—";
  $("#ovMac").textContent = s.mac || "—";
  $("#ovHost").textContent = s.hostname || "—";
  if ($("#ovAdapter")) $("#ovAdapter").textContent = s.adapter || "LAN";
  $("#kIfaces").textContent = s.interfaces;
  $("#kNeighbors").textContent = s.neighbors;
  $("#kRoutes").textContent = s.routes;
  $("#kConns").textContent = s.connections;
  $("#kTcp").textContent = s.tcp_established;
  $("#footTs").textContent = new Date(s.ts * 1000).toLocaleTimeString();

  // Update top status pill
  if (!s.gateway_up) {
    setOverviewAlert("⚠️ Gateway Unreachable", "err");
  } else {
    setOverviewAlert(`Gateway Online (${s.gateway}) · ${s.neighbors} Neighbors`, "ok");
  }
  return s;
}

/* ---------- live monitor ---------- */
function drawLatChart(hist) {
  const svg = $("#latChart");
  if (!svg) return;
  const W = 400, H = 90, pad = 4;
  const pts = (hist || []).filter(p => p.ms != null);
  if (pts.length < 2) {
    svg.innerHTML = `<text x="200" y="48" text-anchor="middle" fill="#5a6a86" font-size="12">collecting samples…</text>`;
    return;
  }
  const max = Math.max(1, ...pts.map(p => p.ms));
  const x = i => pad + (i / (pts.length - 1)) * (W - pad * 2);
  const y = v => H - pad - (v / max) * (H - pad * 2);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.ms).toFixed(1)}`).join(" ");
  const area = `M${x(0).toFixed(1)} ${H - pad} ` +
    pts.map((p, i) => `L${x(i).toFixed(1)} ${y(p.ms).toFixed(1)}`).join(" ") +
    ` L${x(pts.length - 1).toFixed(1)} ${H - pad} Z`;
  // red dots on dropped pings (ms == null) for the same window
  let dots = "";
  (hist || []).forEach((p, i) => {
    if (p.ms == null) {
      const xi = pad + (i / Math.max(1, hist.length - 1)) * (W - pad * 2);
      dots += `<circle cx="${xi.toFixed(1)}" cy="${(H - pad).toFixed(1)}" r="2.5" fill="#f87171"/>`;
    }
  });
  svg.innerHTML = `
    <line x1="${pad}" y1="${(H - pad).toFixed(1)}" x2="${W - pad}" y2="${(H - pad).toFixed(1)}" stroke="#2a3550" stroke-width="1"/>
    <path d="${area}" fill="#a78bfa22"/>
    <path d="${line}" fill="none" stroke="#a78bfa" stroke-width="2"/>
    ${dots}`;
}

function drawBwChart(hist) {
  const svg = $("#bwChart");
  if (!svg) return;
  const W = 400, H = 90, pad = 4;
  if (!hist || hist.length < 2) {
    svg.innerHTML = `<text x="200" y="48" text-anchor="middle" fill="#5a6a86" font-size="12">collecting samples…</text>`;
    return;
  }
  const max = Math.max(1, ...hist.map(p => Math.max(p.rx_bps, p.tx_bps)));
  const x = i => pad + (i / (hist.length - 1)) * (W - pad * 2);
  const y = v => H - pad - (v / max) * (H - pad * 2);
  const path = (key) => hist.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(" ");
  const area = (key) =>
    `M${x(0).toFixed(1)} ${H - pad} ` +
    hist.map((p, i) => `L${x(i).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(" ") +
    ` L${x(hist.length - 1).toFixed(1)} ${H - pad} Z`;
  svg.innerHTML = `
    <path d="${area("rx_bps")}" fill="#38bdf822"/>
    <path d="${path("rx_bps")}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <path d="${area("tx_bps")}" fill="#34d39922"/>
    <path d="${path("tx_bps")}" fill="none" stroke="#34d399" stroke-width="2"/>`;
}

async function loadLive() {
  try {
    const doLat = (loadLive._tick = (loadLive._tick || 0) + 1) % 3 === 1; // ~6s
    const [tr, tt, act, pr, lat, pb] = await Promise.all([
      api("/api/traffic"), api("/api/top-talkers?n=8"), api("/api/activity"),
      api("/api/peers?n=10"), doLat ? api("/api/latency") : Promise.resolve(null),
      api("/api/processes/bandwidth")
    ]);
    const s = tr.sample || {};
    $("#bwRx").textContent = fmtBps(s.rx_bps);
    $("#bwTx").textContent = fmtBps(s.tx_bps);
    $("#bwRxTot").textContent = fmtBytes(s.recv_total);
    $("#bwTxTot").textContent = fmtBytes(s.sent_total);
    drawBwChart(tr.history);
    // A12: peak + average over the visible window (server-computed)
    const st = tr.stats || {};
    if (st.rx_peak != null) $("#bwRxPeak").textContent = fmtBps(st.rx_peak);
    if (st.tx_peak != null) $("#bwTxPeak").textContent = fmtBps(st.tx_peak);
    if (st.rx_avg != null) $("#bwRxAvg").textContent = fmtBps(st.rx_avg);
    if (st.tx_avg != null) $("#bwTxAvg").textContent = fmtBps(st.tx_avg);

    // A10: gateway latency card (only on sampled ticks; ring persists server-side)
    if (lat) {
      const ls = lat.sample || {};
      const lh = lat.history || [];
      $("#latMs").textContent = ls.ms != null ? ls.ms : "—";
      $("#latGw").textContent = ls.host || "—";
      const okMs = lh.filter(p => p.ms != null).map(p => p.ms);
      $("#latAvg").textContent = okMs.length ? Math.round(okMs.reduce((a, b) => a + b, 0) / okMs.length) : "—";
      const up = lh.filter(p => p.reachable).length;
      $("#latUp").textContent = `up ${up}/${lh.length}`;
      $("#latState").textContent = ls.ms != null ? "gateway reachable" : "gateway unreachable";
      drawLatChart(lh);
    }

    // Update Radial Speedometer Gauges
    updateRadialGauges(s.rx_bps, s.tx_bps);

    // Topbar live sparkline
    renderTopbarSparkline(s.rx_bps, s.tx_bps);

    // Mini HUD updates
    if ($("#hudRx")) $("#hudRx").textContent = fmtBps(s.rx_bps);
    if ($("#hudTx")) $("#hudTx").textContent = fmtBps(s.tx_bps);
    if ($("#hudPing") && lat) {
      const ls = lat.sample || {};
      $("#hudPing").textContent = ls.ms != null ? `${ls.ms} ms` : "—";
    }

    const top = pb.processes || [];
    if ($("#hudTopTalker")) {
      $("#hudTopTalker").textContent = top.length ? `Top: ${top[0].process} (${fmtBps(top[0].total_bps)})` : "No active talkers";
    }
    $("#talkers").innerHTML = top.length
      ? top.map(p => `<li>
          <span class="tk-name">${esc(p.process)}</span>
          <span class="tk-n">${fmtBps(p.total_bps)} <span style="font-size:9px;opacity:0.6">(${p.pct}%)</span></span>
        </li>`).join("")
      : `<li class="muted">no connections</li>`;

    const peers = pr.peers || [];
    $("#peersList").innerHTML = peers.length
      ? peers.map(p => `<li>
          <span class="peer-ip" dir="ltr">${esc(p.ip)}</span>
          <span class="peer-tag ${p.local ? "lan" : "ext"}">${p.local ? "LAN" : "external"}</span>
          <span class="peer-meta">${p.established} est · ${p.proto} · ${esc((p.processes || []).slice(0, 2).join(", ")) || "no process"}</span>
          <span class="peer-ports" dir="ltr">${(p.ports || []).slice(0, 6).join(", ")}${(p.ports || []).length > 6 ? "…" : ""}</span>
        </li>`).join("")
      : `<li class="muted">no remote peers with established connections</li>`;

    const evs = act.events || [];
    $("#activityList").innerHTML = evs.length
      ? evs.slice(0, 40).map(e => {
          const ic = e.level === "good" ? "▲" : e.level === "warn" ? "▼" : "•";
          const cls = e.level === "good" ? "good" : e.level === "warn" ? "warn" : "";
          return `<li class="${cls}"><span class="act-ic">${ic}</span>
            <span class="act-msg">${esc(e.msg)}</span>
            <span class="act-ts">${fmtTime(e.ts)}</span></li>`;
        }).join("")
      : `<li class="muted">no changes detected yet… (leave the dashboard open a bit)</li>`;
  } catch (e) { /* server down — ignore on the 2s tick */ }
}

/* ---------- cyber radial gauges ---------- */
function updateRadialGauges(rx_bps, tx_bps) {
  const maxBps = 100 * 1024 * 1024; // 100 Mbps reference scale
  const rxPct = Math.min(1, Math.max(0, rx_bps > 0 ? (Math.log10(rx_bps) / Math.log10(maxBps)) : 0));
  const txPct = Math.min(1, Math.max(0, tx_bps > 0 ? (Math.log10(tx_bps) / Math.log10(maxBps)) : 0));
  const circumference = 188.5;

  const rxPath = $("#gaugeRxPath");
  const txPath = $("#gaugeTxPath");
  if (rxPath) rxPath.style.strokeDashoffset = (circumference * (1 - rxPct)).toFixed(1);
  if (txPath) txPath.style.strokeDashoffset = (circumference * (1 - txPct)).toFixed(1);

  const rxFmt = fmtBps(rx_bps).split(" ");
  const txFmt = fmtBps(tx_bps).split(" ");
  if ($("#gaugeRxVal")) $("#gaugeRxVal").textContent = rxFmt[0] || "0";
  if ($("#gaugeRxUnit")) $("#gaugeRxUnit").textContent = (rxFmt[1] || "B") + "/s";
  if ($("#gaugeTxVal")) $("#gaugeTxVal").textContent = txFmt[0] || "0";
  if ($("#gaugeTxUnit")) $("#gaugeTxUnit").textContent = (txFmt[1] || "B") + "/s";
}

let liveTimer = null;
function startLive() { if (!liveTimer) liveTimer = setInterval(loadLive, 2000); }

/* ---------- topology (Interactive Physics & SVG) ---------- */
async function loadTopology() {
  const t = await api("/api/topology");
  if (physicsViewMode === "physics") {
    initPhysicsTopology(t);
  }
  renderTopo(t);
  $("#topoStats").innerHTML = [
    chip("self", t.self_ip), chip("gw", t.gateway), chip("subnet", t.subnet),
    chip("neighbors", t.nodes.filter(n => n.kind === "device").length),
  ].join("");
  return t;
}
const chip = (k, v) => `<span class="chip">${k}: ${esc(v ?? "—")}</span>`;

function renderTopo(t) {
  const svg = $("#topoSvg");
  const W = svg.clientWidth || 900, H = svg.clientHeight || 480;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const cx = W / 2, cy = H / 2;
  const nodes = t.nodes || [];
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const neighbors = nodes.filter(n => n.kind === "device");
  const gw = nodes.find(n => n.kind === "gateway");
  const self = nodes.find(n => n.kind === "this-pc") || { ip: t.self_ip, label: "This PC" };

  const pos = {};
  pos["self"] = { x: cx, y: cy };
  const baseR = Math.min(W, H) * 0.33;

  // gateway above
  let gwPos = null;
  if (gw) {
    gwPos = { x: cx, y: Math.max(40, cy - baseR * 1.02) };
    pos[gw.id] = gwPos;
  }

  // neighbors positioned cleanly on radial orbits (alternating radius if >= 6 devices so labels never overlap)
  const start = -Math.PI / 2 + 0.45;
  const n = neighbors.length || 1;
  neighbors.forEach((nd, i) => {
    const a = start + (i / n) * (Math.PI * 2);
    const rFactor = (n > 6 && i % 2 === 1) ? 0.76 : 1.02;
    const rX = baseR * 1.08 * rFactor;
    const rY = baseR * 0.88 * rFactor;
    pos[nd.id] = {
      x: Math.max(48, Math.min(W - 48, cx + Math.cos(a) * rX)),
      y: Math.max(48, Math.min(H - 48, cy + Math.sin(a) * rY))
    };
  });

  const colorFor = { "this-pc": "#38bdf8", "gateway": "#34d399", "device": "#a78bfa", "interface": "#fbbf24" };
  const rFor = { "this-pc": 28, "gateway": 22, "device": 16, "interface": 16 };

  // edges
  let edges = "";
  (t.edges || []).forEach(e => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return;
    const isGw = byId[e.to] && byId[e.to].kind === "gateway";
    edges += `<line class="edge ${isGw ? "gw" : ""}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>`;
  });

  // nodes
  let nodesSvg = "";
  nodes.forEach(nd => {
    const p = pos[nd.id]; if (!p) return;
    const c = colorFor[nd.kind] || "#8494ad";
    const r = rFor[nd.kind] || 16;
    const tip = [
      nd.label, nd.ip, nd.mac ? `MAC ${nd.mac}` : "",
      nd.vendor ? nd.vendor : "", nd.ms != null ? `${nd.ms} ms` : "",
    ].filter(Boolean).join(" · ");
    const vendorShort = nd.vendor ? (nd.vendor.length > 15 ? nd.vendor.slice(0, 14) + "…" : nd.vendor) : "";
    nodesSvg += `
      <g class="node" data-id="${esc(nd.id)}">
        <title>${esc(tip)}</title>
        <circle cx="${p.x}" cy="${p.y}" r="${r + 5}" fill="${c}18" />
        <circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${c}2a" stroke="${c}" stroke-width="2.5"/>
        <text x="${p.x}" y="${p.y + 4}" text-anchor="middle" style="fill:${c};font-weight:700;font-size:${r > 20 ? 12 : 10}px">
          ${nd.kind === "this-pc" ? "PC" : (nd.kind === "gateway" ? "GW" : "•")}
        </text>
        <text class="sub-lbl" x="${p.x}" y="${p.y + r + 13}" text-anchor="middle" style="fill:#e2e8f0;font-weight:600;font-size:10px">${esc(nd.label)}</text>
        ${vendorShort ? `<text class="sub-vnd" x="${p.x}" y="${p.y + r + 24}" text-anchor="middle" style="fill:#94a3b8;font-size:8.5px">${esc(vendorShort)}</text>` : ""}
      </g>`;
  });

  svg.innerHTML = `<defs>
      <radialGradient id="glow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#38bdf826"/><stop offset="100%" stop-color="transparent"/>
      </radialGradient>
      <radialGradient id="gwglow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#34d39922"/><stop offset="100%" stop-color="transparent"/>
      </radialGradient>
    </defs>
    <rect x="0" y="0" width="${W}" height="${H}" fill="#090f1c"/>
    <circle cx="${cx}" cy="${cy}" r="${baseR * 1.1}" fill="url(#glow)"/>
    <circle cx="${cx}" cy="${cy}" r="${baseR * 0.3}" fill="none" stroke="var(--accent)" stroke-width="1.5" opacity="0.6">
      <animate attributeName="r" from="20" to="${baseR * 1.15}" dur="3.5s" repeatCount="indefinite"/>
      <animate attributeName="opacity" from="0.8" to="0" dur="3.5s" repeatCount="indefinite"/>
    </circle>
    <circle cx="${cx}" cy="${cy}" r="${baseR * 0.3}" fill="none" stroke="var(--accent2)" stroke-width="1" opacity="0.6">
      <animate attributeName="r" from="20" to="${baseR * 1.15}" begin="1.75s" dur="3.5s" repeatCount="indefinite"/>
      <animate attributeName="opacity" from="0.8" to="0" begin="1.75s" dur="3.5s" repeatCount="indefinite"/>
    </circle>
    ${gwPos ? `<circle cx="${gwPos.x}" cy="${gwPos.y}" r="60" fill="url(#gwglow)"/>` : ""}
    ${edges}${nodesSvg}`;

  // click node -> jump to devices tab and highlight device
  $$("#topoSvg .node").forEach(g => g.addEventListener("click", () => {
    const id = g.dataset.id;
    const nd = byId[id];
    if (nd && nd.kind === "device") { switchTab("devices"); highlightDevice(nd.ip); }
  }));
}

function switchTab(name) {
  const b = $(`.tab[data-tab="${name}"]`);
  if (b) b.click();
}

/* ---------- devices ---------- */
let devList = []; // full device list (This PC + gateway + neighbors), kept for filter/export
async function loadDevices() {
  const t = await api("/api/topology");
  const rows = t.nodes.filter(n => n.kind === "device");
  devList = [
    { ip: t.self_ip, kind: "this-pc", label: "This PC", mac: (t.nodes.find(n=>n.kind==="this-pc")||{}).mac, vendor: "", type: "—", reach: true, ms: 0, alias: "", os_guess: "Windows" },
    ...(t.gateway ? [{ ip: t.gateway, kind: "gateway", label: "Gateway", mac: (t.nodes.find(n=>n.kind==="gateway")||{}).mac, vendor: (t.nodes.find(n=>n.kind==="gateway")||{}).vendor, type: "—", reach: true, ms: null, alias: "", os_guess: (t.nodes.find(n=>n.kind==="gateway")||{}).os_guess }] : []),
    ...rows.map(r => ({ ip: r.ip, kind: r.kind, label: r.label, mac: r.mac, vendor: r.vendor, type: r.type, reach: r.reachable, ms: r.ms, alias: r.alias, os_guess: r.os_guess })),
  ];
  populateVendorFilter();
  applyDeviceFilter();
}

/* A13: pure, dependency-free filter — testable in Node without a DOM. */
function filterDevices(list, f) {
  f = f || {};
  const q = (f.q || "").trim().toLowerCase();
  const status = f.status || "ALL";
  const vendor = f.vendor || "ALL";
  return (list || []).filter(d => {
    if (q) {
      const hay = [d.ip, d.mac, d.vendor, d.label].map(x => (x || "").toLowerCase()).join(" ");
      if (!hay.includes(q)) return false;
    }
    if (status === "up" && !d.reach) return false;
    if (status === "down" && d.reach) return false;
    if (vendor === "unknown" && (d.vendor || "").trim()) return false;
    if (vendor !== "ALL" && vendor !== "unknown" && (d.vendor || "") !== vendor) return false;
    return true;
  });
}

function renderDeviceTable(list) {
  const body = $("#devBody");
  if (!list.length) {
    body.innerHTML = `<tr><td colspan="9" class="muted">No devices match the current filter. Clear it to see all.</td></tr>`;
    return;
  }
  body.innerHTML = list.map((d, i) => `<tr>
    <td>
      <div style="display:flex;flex-direction:column">
        <b style="cursor:pointer;text-decoration:underline dashed" onclick="promptAlias('${esc(d.mac)}', '${esc(d.alias || d.ip)}')">${esc(d.alias || d.ip)}</b>
        ${d.alias ? `<span style="font-size:10.5px;color:var(--muted)">${esc(d.ip)}</span>` : ""}
      </div>
      ${d.is_new ? `<span class="badge-new-device" style="margin-left:6px" title="Unrecognized / newly connected MAC address">⚠️ NEW</span>` : ""}
    </td>
    <td>${badge(d.kind, d.kind === "this-pc" ? "b-this" : d.kind === "gateway" ? "b-gw" : "b-dev")}</td>
    <td class="mono">${esc(d.mac) || "—"}</td>
    <td>${esc(d.vendor) || "<span class='muted'>—</span>"}</td>
    <td>${d.os_guess ? `<span class="badge" style="font-size:10px;background:rgba(255,255,255,0.1)">${esc(d.os_guess)}</span>` : "<span class='muted'>—</span>"}</td>
    <td>${d.reach ? badge("up", "b-yes") : badge("down", "b-no")}</td>
    <td class="mono">${d.ms != null ? d.ms + " ms" : "—"}</td>
    <td id="ptr-${i}" class="muted">–</td>
    <td id="ports-${i}" class="muted">–</td>
    <td style="white-space:nowrap">
      <button class="btn" style="padding:4px 8px;font-size:11px" onclick="pingOne('${esc(d.ip)}')">ping</button>
      <button class="btn" style="padding:4px 8px;font-size:11px" onclick="openPortScanModal('${esc(d.ip)}')">🔍 Scan</button>
      ${d.is_new && d.mac ? `<button class="btn" style="padding:4px 8px;font-size:11px;color:var(--ok);border-color:var(--ok)" onclick="acknowledgeDevice('${esc(d.mac)}')" title="Mark this device as trusted / known">✓ Trust</button>` : ""}
      ${d.mac ? `<button class="btn btn-accent" style="padding:4px 8px;font-size:11px" onclick="triggerWolFromDevice('${esc(d.mac)}')" title="Wake this device via Magic Packet">⚡ WOL</button>` : ""}
    </td>
  </tr>`).join("");
  list.forEach((d, i) => { if (d.ip && d.ip !== "127.0.0.1") resolvePTR(i, d.ip); });
}

async function acknowledgeDevice(mac) {
  try {
    const res = await api(`/api/devices/acknowledge?mac=${encodeURIComponent(mac)}`);
    if (res.ok) {
      loadDevices();
      loadTopology();
    }
  } catch (e) {
    console.error("Acknowledge error:", e);
  }
}

window.triggerWolFromDevice = async function(mac) {
  if (!confirm(`Send Wake-On-LAN (WOL) Magic Packet to MAC: ${mac}?`)) return;
  try {
    const res = await api(`/api/profiles/wol?mac=${encodeURIComponent(mac)}`);
    if (res.ok) alert(`WOL packet sent successfully to ${mac}!`);
    else alert(`Error: ${res.error}`);
  } catch (e) {
    alert(`Failed to send WOL: ${e}`);
  }
};

window.promptAlias = async function(mac, current) {
  if (!mac) return alert("No MAC address available for this device.");
  const alias = prompt("Enter a custom name (alias) for this device:", current !== "null" ? current : "");
  if (alias === null) return; // Cancelled
  
  await api(`/api/devices/alias?mac=${encodeURIComponent(mac)}&alias=${encodeURIComponent(alias)}`, { method: "POST" });
  loadDevices();
  loadTopology();
};

const updateVendorsBtn = $("#updateVendorsBtn");
if (updateVendorsBtn) {
  updateVendorsBtn.onclick = async () => {
    updateVendorsBtn.disabled = true;
    updateVendorsBtn.textContent = "🔄 Updating...";
    try {
      const r = await api("/api/vendor/update");
      alert(r.msg + "\n\nIt runs in the background. Refresh the page in a few seconds.");
    } catch (e) {
      alert("Error: " + e.message);
    }
    updateVendorsBtn.disabled = false;
    updateVendorsBtn.textContent = "🔄 Update Vendors";
  };
}

/* A13: re-render the visible table from the current filter controls. */
function applyDeviceFilter() {
  const f = {
    q: ($("#devSearch") ? $("#devSearch").value : ""),
    status: ($("#devStatus") ? $("#devStatus").value : "ALL"),
    vendor: ($("#devVendor") ? $("#devVendor").value : "ALL"),
  };
  const list = filterDevices(devList, f);
  renderDeviceTable(list);
  const c = $("#devCount");
  if (c) c.textContent = `${list.length} / ${devList.length}`;
}

/* A13: build the vendor <select> options from the current device list. */
function populateVendorFilter() {
  const sel = $("#devVendor");
  if (!sel) return;
  const vendors = Array.from(new Set(devList.map(d => (d.vendor || "").trim()).filter(Boolean))).sort();
  const prev = sel.value || "ALL";
  sel.innerHTML = `<option value="ALL">vendor: all</option>` +
    vendors.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("") +
    (devList.some(d => !(d.vendor || "").trim()) ? `<option value="unknown">vendor: unknown</option>` : "");
  if (Array.from(sel.options).some(o => o.value === prev)) sel.value = prev;
}

/* A14: pure CSV builder (RFC 4180 quoting) — testable in Node without a DOM. */
function devicesToCsv(list) {
  const head = ["IP", "Kind", "MAC", "Vendor", "Status", "Latency_ms", "ARP_type"];
  const escCsv = (v) => {
    v = v == null ? "" : String(v);
    return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  };
  const lines = [head.join(",")];
  (list || []).forEach(d => lines.push([
    d.ip, d.kind, d.mac || "", d.vendor || "", d.reach ? "up" : "down",
    (d.ms != null ? d.ms : ""), d.type || "",
  ].map(escCsv).join(",")));
  // BOM so Excel opens UTF-8 correctly
  return "\uFEFF" + lines.join("\r\n");
}

function downloadText(text, filename, mime) {
  const blob = new Blob([text], { type: mime });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function highlightDevice(ip) {
  const trs = $$("#devBody tr");
  trs.forEach(tr => tr.style.outline = "");
  const tr = trs.find(r => r.textContent.includes(ip));
  if (tr) { tr.style.outline = "2px solid #38bdf8"; tr.scrollIntoView({ block: "center" }); }
}
async function pingOne(ip) {
  const r = await api(`/api/ping?ip=${encodeURIComponent(ip)}`);
  highlightDevice(ip);
  // patch latency cell (6th column, index 5)
  const tr = $$("#devBody tr").find(r => r.textContent.includes(ip));
  if (tr && tr.children[5]) tr.children[5].textContent = r.reachable ? `${r.avg_ms} ms` : "timeout";
}
/* A9: reverse-DNS (PTR) for a row — fills the PTR column, no reload */
async function resolvePTR(i, ip) {
  const cell = $(`#ptr-${i}`);
  if (cell) cell.textContent = "…";
  const r = await api(`/api/ptr?ip=${encodeURIComponent(ip)}`);
  const c = $(`#ptr-${i}`);
  if (!c) return;
  if (r.found && r.name) {
    c.innerHTML = badge(r.name, "b-yes");
    c.title = r.name;
  } else {
    c.innerHTML = "<span class='muted'>—</span>";
  }
}
/* A8: TCP port scan for a row — fills the Ports column with open ports */
async function scanPorts(i, ip) {
  const cell = $(`#ports-${i}`);
  if (cell) cell.innerHTML = "<span class='muted'>scanning…</span>";
  const r = await api(`/api/portscan?ip=${encodeURIComponent(ip)}`);
  const c = $(`#ports-${i}`);
  if (!c) return;
  if (r.error) { c.innerHTML = `<span class="muted">${esc(r.error)}</span>`; return; }
  if (r.open_count > 0) {
    c.innerHTML = r.open_ports.slice(0, 8).map(p => badge(p, "b-gw")).join(" ");
    if (r.open_ports.length > 8) c.innerHTML += `<span class="muted">+${r.open_ports.length - 8}</span>`;
    c.title = "open: " + r.open_ports.join(", ");
  } else {
    c.innerHTML = `<span class="muted">none open</span>`;
  }
}

/* ---------- connections ---------- */
let connFilter = "ALL";
async function loadConnections() {
  const d = await api("/api/connections");
  loadProcessBandwidth();
  const conns = d.connections || [];
  $("#connCount").textContent = conns.length;
  const states = {};
  conns.forEach(c => states[c.state] = (states[c.state] || 0) + 1);
  const proto = { TCP: 0, UDP: 0 };
  conns.forEach(c => proto[c.proto] = (proto[c.proto] || 0) + 1);
  const chips = ["ALL", "ESTABLISHED", "LISTENING", "TCP", "UDP"];
  $("#connChips").innerHTML = chips.map(c =>
    `<span class="chip-f ${c === connFilter ? "on" : ""}" data-f="${c}">${c}${
      c === "TCP" || c === "UDP" ? ` (${proto[c] || 0})` : states[c] ? ` (${states[c]})` : ""}</span>`
  ).join("");
  $$("#connChips .chip-f").forEach(el => el.onclick = () => { connFilter = el.dataset.f; loadConnections(); });
  const filtered = conns.filter(c =>
    connFilter === "ALL" ? true :
    (connFilter === "TCP" || connFilter === "UDP") ? c.proto === connFilter :
    c.state === connFilter);
  $("#connBody").innerHTML = filtered.slice(0, 300).map(c => `<tr>
    <td>${badge(c.proto, c.proto === "TCP" ? "b-tcp" : "b-udp")}</td>
    <td>${esc(c.local)}</td><td>${esc(c.remote)}</td>
    <td>${badge(c.state, c.state === "ESTABLISHED" ? "b-est" : c.state === "LISTENING" ? "b-list" : "")}</td>
    <td>${esc(c.pid)}</td>
    <td>${esc(c.process) || "<span class='muted'>—</span>"}</td>
    <td style="white-space:nowrap">
      ${(c.pid && parseInt(c.pid) > 4) ? `<button class="btn" style="padding:2px 6px;font-size:10.5px;color:var(--err);border-color:#5c1d24" onclick="killProcess(${c.pid},'${esc(c.process)}')">✕ Kill</button>` : ""}
    </td></tr>`).join("") || `<tr><td colspan="7" class="muted">none</td></tr>`;
}

window.killProcess = async function(pid, name) {
  if (!confirm(`Terminate process "${name || 'PID ' + pid}" (PID: ${pid})?`)) return;
  try {
    const r = await api(`/api/process/kill?pid=${pid}`);
    alert(r.ok ? `Process ${name || pid} terminated.` : `Kill failed: ${r.output || r.error}`);
    loadConnections();
    loadOverview();
  } catch (e) {
    alert("Error: " + e.message);
  }
};

/* ---------- smart ai network explainer ---------- */
async function loadExplainer() {
  const sumEl = $("#aiExpSummary"), scoreEl = $("#aiExpScore"), chipsEl = $("#aiExpChips");
  if (!sumEl || !chipsEl) return;
  try {
    const d = await api("/api/explainer");
    sumEl.textContent = d.summary_text_en || d.summary_text_he;
    if (scoreEl) {
      scoreEl.textContent = `${d.score} / 100`;
      scoreEl.className = `badge ${d.score >= 85 ? "b-est" : d.score >= 70 ? "b-dev" : "b-no"}`;
    }
    const chips = d.insights_en || d.insights_he || [];
    chipsEl.innerHTML = chips.map(c => `
      <div class="ai-exp-chip ${c.type}" title="${esc(c.desc)}">
        <span>${c.icon}</span>
        <b>${esc(c.title)}</b>
      </div>
    `).join("");
  } catch (e) {
    console.error("Explainer error:", e);
  }
}

/* ---------- routes ---------- */
async function loadRoutes() {
  const d = await api("/api/routes");
  const r = d.routes || [];
  $("#routeCount").textContent = r.length;
  const order = ["0.0.0.0", ...r.map(x => x.dest)];
  const sorted = [...r].sort((a, b) => {
    const ai = a.gateway === "On-link" ? 1 : 0, bi = b.gateway === "On-link" ? 1 : 0;
    return ai - bi || (a.dest < b.dest ? -1 : 1);
  });
  $("#routeBody").innerHTML = sorted.map(x => `<tr>
    <td>${esc(x.dest)}</td><td>${esc(x.netmask)}</td>
    <td>${x.gateway === "On-link" ? badge("On-link", "b-list") : esc(x.gateway)}</td>
    <td>${esc(x.iface)}</td><td>${esc(x.metric)}</td></tr>`).join("");
}

/* ---------- interfaces ---------- */
async function loadInterfaces() {
  const d = await api("/api/interfaces");
  const ifaces = d.interfaces || [];
  if (!ifaces.length) {
    const s = await api("/api/summary");
    $("#ifaceCards").innerHTML = `<div class="icard">
      <h4><span class="dot"></span>Primary</h4>
      ${kv("IP", s.self_ip)}${kv("Gateway", s.gateway)}${kv("Subnet", s.subnet)}${kv("MAC", s.mac)}</div>`;
    return;
  }
  $("#ifaceCards").innerHTML = ifaces.map(i => `
    <div class="icard ${i.media_down ? "down" : "up"}">
      <h4><span class="dot ${i.media_down ? "down" : "up"}"></span>${esc(i.name)}
        ${i.media_down ? badge("down", "b-no") : (i.ip ? badge("up", "b-yes") : "")}</h4>
      ${kv("IPv4", i.ip)}${kv("Gateway", i.gw)}${kv("Subnet", i.subnet)}
      ${kv("MAC", i.mac)}${kv("DNS", (i.dns || []).join(", "))}${kv("DHCP", i.dhcp)}
      <div style="margin-top:10px;display:flex;justify-content:flex-end">
        <button class="btn" style="padding:4px 10px;font-size:11px" onclick="restartAdapter('${esc(i.name)}')">🔀 Restart Adapter</button>
      </div>
    </div>`).join("");
}
const kv = (k, v) => v ? `<div class="row-kv"><span class="k">${k}</span><span class="v">${esc(v)}</span></div>` : "";

window.restartAdapter = async function(name) {
  if (!confirm(`Are you sure you want to power-cycle and restart adapter "${name}"? Network will briefly disconnect.`)) return;
  try {
    const r = await api(`/api/interfaces/restart?name=${encodeURIComponent(name)}`);
    alert(r.ok ? `Adapter "${name}" restarted successfully!` : `Restart error: ${r.output || r.error}`);
    loadInterfaces();
    loadOverview();
  } catch (e) {
    alert("Error restarting adapter: " + e.message);
  }
};

/* ---------- diagnostics ---------- */
async function runPing() {
  const ip = $("#pingIp").value.trim() || "127.0.0.1";
  $("#pingOut").textContent = "…";
  const r = await api(`/api/ping?ip=${encodeURIComponent(ip)}`);
  $("#pingOut").textContent = `IP: ${r.ip}\nReachable: ${r.reachable ? "YES" : "NO"}\nAvg: ${r.avg_ms ?? "—"} ms\nLoss: ${r.loss_pct ?? "—"}%`;
}
async function runDns() {
  const h = $("#dnsHost").value.trim() || "google.com";
  $("#dnsOut").textContent = "…";
  const r = await api(`/api/dns?host=${encodeURIComponent(h)}`);
  $("#dnsOut").textContent = `Host: ${r.host}\n${r.cname ? "CNAME: " + r.cname + "\n" : ""}Addresses:\n  ${(r.answers || []).join("\n  ") || "(none)"}`;
}
async function runTr() {
  const h = $("#trHost").value.trim() || "8.8.8.8";
  $("#trOut").textContent = "running traceroute… (can take a few seconds)";
  const r = await api(`/api/traceroute?host=${encodeURIComponent(h)}`);
  $("#trOut").textContent = (r.hops || []).map(x => `#${x.hop}  ${x.raw}`).join("\n") || "(no hops)";
}

/* ---------- raw cmd ---------- */
let allowed = [];
async function loadRaw() {
  const d = await api("/api/commands");
  allowed = d.allowed;
  $("#rawPick").innerHTML = allowed.map(c =>
    `<span class="chip-f" data-cmd="${esc(c)}">${esc(c)}</span>`).join("");
  $$("#rawPick .chip-f").forEach(el => el.onclick = () => runRaw(el.dataset.cmd));
}
async function runRaw(cmd) {
  $("#rawOut").textContent = `running ${cmd} …`;
  const r = await api(`/api/raw?cmd=${encodeURIComponent(cmd)}`);
  $("#rawOut").textContent = (r.output || r.error || "").toString();
}

/* ---------- actions ---------- */
$("#refreshBtn").onclick = async () => {
  await fetch("/api/refresh", { method: "POST" });
  setStatus(true, "refreshing…");
  await loadAll();
  setStatus(true);
};
$("#topoSvgBtn").onclick = () => {
  const svg = $("#topoSvg");
  if (!svg || !svg.innerHTML) return;
  const clone = svg.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const s = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([s], { type: "image/svg+xml;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `netvisual-topology-${Date.now()}.svg`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
/* A11: show/hide + paint the deep-scan progress bar from /api/scan-status. */
let scanPoller = null;
function showScanProgress(on) {
  const box = $("#scanProgress");
  if (!box) return;
  box.hidden = !on;
}
function paintScan(st) {
  const pct = Math.max(0, Math.min(100, st.percent || 0));
  const fill = $("#scanFill"), meta = $("#scanMeta"), p = $("#scanPct");
  if (fill) { fill.style.width = pct + "%"; fill.classList.toggle("done", !st.running && pct >= 100); }
  if (p) p.textContent = pct + "%";
  if (meta) meta.textContent = st.running
    ? `scanning subnet… ${st.done}/${st.total} · found ${st.found}`
    : `done — ${st.found} live host(s)`;
}
function startScanPolling() {
  if (scanPoller) clearInterval(scanPoller);
  const tick = async () => {
    try {
      const st = await api("/api/scan-status");
      paintScan(st);
      if (!st.running && scanPoller) {
        clearInterval(scanPoller); scanPoller = null;
        setTimeout(() => showScanProgress(false), 1200);
      }
    } catch (e) { /* server hiccup — keep polling */ }
  };
  tick();
  scanPoller = setInterval(tick, 300);
}

$("#deepScanBtn").onclick = async () => {
  const b = $("#deepScanBtn");
  b.disabled = true; b.textContent = "🔍 scanning subnet…";
  showScanProgress(true);
  startScanPolling();
  try {
    const t = await api("/api/topology?sweep=1");
    renderTopo(t);
    loadDevices();
    setStatus(true, "deep scan done");
  } catch (e) {
    setStatus(false, "scan failed");
  } finally {
    b.disabled = false; b.textContent = "🔍 Deep Scan";
  }
};

/* A14: export the full (unfiltered) device list as CSV. */
$("#csvBtn").onclick = () => {
  if (!devList.length) { setStatus(false, "no devices to export"); return; }
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  downloadText(devicesToCsv(devList), `netvisual-devices-${ts}.csv`, "text/csv;charset=utf-8");
};

/* A13: live filter controls. */
$("#devSearch").addEventListener("input", applyDeviceFilter);
$("#devStatus").addEventListener("change", applyDeviceFilter);
$("#devVendor").addEventListener("change", applyDeviceFilter);
$("#exportBtn").onclick = async () => {
  const [s, t, c, r, i] = await Promise.all([
    api("/api/summary"), api("/api/topology"), api("/api/connections"),
    api("/api/routes"), api("/api/interfaces")]);
  const blob = new Blob([JSON.stringify({ s, t, c, r, i }, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `netvisual-${Date.now()}.json`; a.click();
};

/* ---------- trends (persistent history) ---------- */
let trRange = "6h";
let trLoaded = false;

function drawTrChart(svg, pts, opts) {
  opts = opts || {};
  if (!svg) return;
  const W = 760, H = 200, padX = 8, padY = 14;
  const vals = pts.map(p => p).filter(v => v != null);
  if (!pts.length || vals.length < 2) {
    svg.innerHTML = `<text x="${W/2}" y="${H/2}" text-anchor="middle" fill="#5a6a86" font-size="13">no data in this window</text>`;
    return;
  }
  const max = Math.max(1, ...vals.map(v => Math.abs(v)));
  const min = opts.floor != null ? opts.floor : Math.min(0, ...vals);
  const span = (max - min) || 1;
  const x = i => padX + (pts.length === 1 ? 0 : (i / (pts.length - 1)) * (W - padX * 2));
  const y = v => H - padY - ((v - min) / span) * (H - padY * 2);
  const line = pts.map((v, i) => {
    if (v == null) return null;
    const prevOk = i > 0 && pts[i - 1] != null;
    return `${prevOk ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
  }).filter(Boolean).join(" ");
  const base = H - padY;
  const area = `M${x(0).toFixed(1)} ${base} ` +
    pts.map((v, i) => v == null ? "" : `L${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ") +
    ` L${x(pts.length - 1).toFixed(1)} ${base} Z`;
  const color = opts.color || "#6ea8fe";
  let grid = "";
  for (let g = 0; g <= 3; g++) {
    const gy = padY + (g / 3) * (H - padY * 2);
    grid += `<line x1="${padX}" y1="${gy.toFixed(1)}" x2="${W - padX}" y2="${gy.toFixed(1)}" stroke="#223049" stroke-width="1"/>`;
  }
  svg.innerHTML = `${grid}
    <path d="${area}" fill="${color}1f"/>
    <path d="${line}" fill="none" stroke="${color}" stroke-width="2"/>`;
}

function trKpi(label, val, sub) {
  return `<div class="tr-kpi"><b>${val}</b><span>${label}</span>${sub ? `<small>${sub}</small>` : ""}</div>`;
}

async function loadTrends(range) {
  range = range || trRange;
  const d = await api(`/api/history?range=${encodeURIComponent(range)}`);
  const info = d.info || {};
  if ($("#trInterval")) $("#trInterval").textContent = info.interval_s ?? "30";
  if ($("#trRetention")) $("#trRetention").textContent = info.retention_days ?? "30";
  const s = d.stats || {};
  const k = $("#trKpis");
  if (s.points === 0) {
    k.innerHTML = "";
    $("#trEmpty").hidden = false;
  } else {
    $("#trEmpty").hidden = true;
    k.innerHTML =
      trKpi("Data ↓", fmtBytes(s.data_rx_bytes), "received") +
      trKpi("Data ↑", fmtBytes(s.data_tx_bytes), "sent") +
      trKpi("Peak ↓", fmtBps(s.rx_peak) + "/s", "") +
      trKpi("Peak ↑", fmtBps(s.tx_peak) + "/s", "") +
      trKpi("Avg ↓", fmtBps(s.rx_avg) + "/s", "mean rate") +
      trKpi("GW latency", s.lat_avg != null ? s.lat_avg + " ms" : "—",
            s.lat_peak != null ? "peak " + s.lat_peak + "ms" : "") +
      trKpi("GW up", s.gw_up_pct != null ? s.gw_up_pct + "%" : "—", "reachability") +
      trKpi("Devices peak", s.devices_peak, "max hosts") +
      trKpi("Samples", s.points, s.span_s ? (s.span_s / 3600).toFixed(1) + "h span" : "");
  }
  const series = d.series || [];
  drawTrChart($("#trBwChart"), series.map(p => p.rx), { color: "#34d399" });
  drawTrChart($("#trLatChart"), series.map(p => p.lat), { color: "#a78bfa", floor: 0 });
  drawTrChart($("#trDevChart"), series.map(p => p.devices), { color: "#6ea8fe", floor: 0 });
  drawTrChart($("#trConnChart"), series.map(p => p.connections), { color: "#fbbf24", floor: 0 });
  trLoaded = true;
  return d;
}

document.querySelectorAll(".tr-range").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".tr-range").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  trRange = b.dataset.range;
  loadTrends(trRange);
  loadStage1(trRange);
}));

/* load trends the first time the tab is shown, then keep it fresh every 60s */
document.querySelector('.tab[data-tab="trends"]')?.addEventListener("click", () => {
  loadTrends(trRange); loadStage1(trRange);
});
setInterval(() => { if (trLoaded) { loadTrends(trRange); loadStage1(trRange); } }, 60000);

/* ---------- stage-1 insights (status / alerts / devices / baseline / anomaly) ---------- */
function s1Badge(el, text, cls) {
  if (!el) return;
  el.textContent = text;
  el.className = "s1-badge" + (cls ? " " + cls : "");
}
function s1Item(sev, msg, th) {
  const cls = sev || "info";
  return `<div class="s1-item ${cls}"><span class="s1-sev"></span><span class="s1-msg">${msg}</span>${th ? `<span class="s1-th">${th}</span>` : ""}</div>`;
}
function s1TimeAgo(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.round((Date.now() / 1000) - ts));
  if (s < 60) return s + "s ago";
  if (s < 3600) return Math.round(s / 60) + "m ago";
  if (s < 86400) return Math.round(s / 3600) + "h ago";
  return Math.round(s / 86400) + "d ago";
}

/* Gateway up/down timeline drawn as colored segments across the window */
function drawStatusTimeline(svg, d) {
  if (!svg) return;
  const segs = (d && d.segments) || [];
  if (!segs.length) { svg.innerHTML = ""; return; }
  const t0 = segs[0].start_ts, t1 = segs[segs.length - 1].end_ts;
  const span = Math.max(1, t1 - t0);
  const W = 760, H = 46, pad = 6, top = 8, bh = H - top - 6;
  const color = { up: "var(--ok)", down: "var(--err)", unknown: "#44536e" };
  let out = `<line x1="${pad}" y1="${H/2}" x2="${W-pad}" y2="${H/2}" stroke="#1b2740" stroke-width="1"/>`;
  for (const s of segs) {
    const x0 = pad + ((s.start_ts - t0) / span) * (W - pad * 2);
    const x1 = pad + ((s.end_ts - t0) / span) * (W - pad * 2);
    out += `<rect x="${x0.toFixed(1)}" y="${top}" width="${Math.max(1, x1 - x0).toFixed(1)}" height="${bh}" rx="3" fill="${color[s.state] || "#44536e"}" opacity="0.92"/>`;
  }
  svg.innerHTML = out;
}

async function loadStage1(range) {
  range = range || trRange;
  if ($("#trS1Note")) $("#trS1Note").textContent = "for the " + range + " window";
  const r = encodeURIComponent(range);
  // fetch trends first so the anomaly check can use the current RX value
  const hist = await api(`/api/history?range=${r}`).catch(() => null);
  const lastRx = (hist && hist.series && hist.series.length) ? hist.series[hist.series.length - 1].rx : null;
  const [alerts, status, devices, baseline, anomaly] = await Promise.allSettled([
    api(`/api/alerts?range=${r}`),
    api(`/api/status?range=${r}`),
    api(`/api/devices?range=${r}`),
    api(`/api/baseline?range=${r}&metric=rx_bps`),
    lastRx != null ? api(`/api/anomaly?range=${r}&metric=rx_bps&value=${lastRx}`) : Promise.reject("no value"),
  ]);
  if (alerts.status === "fulfilled") renderAlerts(alerts.value);
  if (status.status === "fulfilled") renderStatus(status.value);
  if (devices.status === "fulfilled") renderDeviceChanges(devices.value);
  if (baseline.status === "fulfilled") renderBaseline(baseline.value);
  if (anomaly.status === "fulfilled") renderAnomaly(anomaly.value);
  else if (lastRx == null) renderAnomaly({ points: 0 });
}

function renderAlerts(d) {
  const list = $("#trAlerts"), badge = $("#trAlertCount"), card = $("#trAlertCard");
  const alerts = (d && d.alerts) || [];
  if (!d || d.points === 0) { list.innerHTML = '<span class="muted">no data in window</span>'; s1Badge(badge, "—", ""); return; }
  if (alerts.length === 0) {
    list.innerHTML = '<div class="s1-item" style="justify-content:center"><span class="muted">All clear — no active alerts</span></div>';
    s1Badge(badge, "0", "ok");
    if (card) card.style.borderColor = "";
  } else {
    list.innerHTML = alerts.map(a => s1Item(a.severity, a.detail || a.id, a.threshold)).join("");
    s1Badge(badge, alerts.length, alerts.some(a => a.severity === "critical") ? "err" : "warn");
  }
}

function renderStatus(d) {
  drawStatusTimeline($("#trStatusTimeline"), d);
  const badge = $("#trStatusUp"), sub = $("#trStatusSub");
  if (!d || d.points === 0) { s1Badge(badge, "—", ""); if (sub) sub.textContent = "no data in window"; return; }
  const up = d.up_pct;
  const badgeTxt = up == null ? "n/a" : up + "% up";
  s1Badge(badge, badgeTxt, up == null ? "" : (up >= 99.5 ? "ok" : (up >= 95 ? "warn" : "err")));
  const downSegs = (d.segments || []).filter(s => s.state === "down");
  let msg = `${downSegs.length} down period${downSegs.length === 1 ? "" : "s"} · ${Math.round(d.total_down_s)}s total down`;
  if (up != null) msg += ` · ${up}% reachable`;
  if (sub) sub.textContent = msg;
}

function renderDeviceChanges(d) {
  const list = $("#trDevEvents"), badge = $("#trDevCount");
  const events = (d && d.events) || [];
  if (!events.length) {
    list.innerHTML = '<div class="s1-item" style="justify-content:center"><span class="muted">No device joins/leaves in window</span></div>';
    s1Badge(badge, "0", "ok");
    return;
  }
  list.innerHTML = events.map(e =>
    s1Item(e.event, `${e.ip}`, s1TimeAgo(e.ts))).join("");
  s1Badge(badge, d.event_count, "warn");
}

function renderBaseline(d) {
  const wrap = $("#trBaselineBars");
  const byHour = (d && d.by_hour) || [];
  if (!byHour.length) { wrap.innerHTML = '<span class="muted">no data in window</span>'; return; }
  const max = Math.max(1, ...byHour.map(h => h.avg));
  // map 24 hour slots; fill missing with 0 height
  const slots = Array.from({ length: 24 }, (_, h) => {
    const row = byHour.find(b => b.hour === h);
    const val = row ? row.avg : null;
    const hgt = val == null ? 0 : Math.max(2, (val / max) * 100);
    const tip = val == null ? `${h}:00 · —` : `${h}:00 · ${fmtBps(val)}/s avg`;
    return `<div class="s1-bar" style="height:${hgt}%" title="${tip}"><span>${tip}</span></div>`;
  }).join("");
  wrap.innerHTML = slots;
}

function renderAnomaly(d) {
  const badge = $("#trAnomalyBadge"), det = $("#trAnomalyDetail");
  if (!d || d.points < 5) { s1Badge(badge, "n/a", ""); if (det) det.textContent = "need ≥5 samples to compute baseline"; return; }
  const z = d.z, anom = d.is_anomaly;
  s1Badge(badge, z == null ? "—" : "z=" + z, anom ? "warn" : "ok");
  if (det) det.textContent = `current vs mean ${fmtBps(d.mean)}/s (σ ${fmtBps(d.std)}/s) · threshold z≥${d.threshold}`;
}

/* ---------- security inspector ---------- */
async function loadSecurityAudit() {
  const btn = $("#runSecAuditBtn");
  if (btn) btn.textContent = "🛡️ Auditing…";
  try {
    const d = await api("/api/security/audit");
    if ($("#secScore")) {
      $("#secScore").textContent = d.grade || "A+";
      $("#secScore").className = (d.score >= 85) ? "kpi-ok" : (d.score >= 70) ? "kpi-warn" : "kpi-bad";
    }
    if ($("#secScoreSub")) $("#secScoreSub").textContent = `Posture Score: ${d.score}/100`;
    if ($("#secThreatCount")) $("#secThreatCount").textContent = d.threat_count || 0;
    if ($("#secThreatBadge")) {
      $("#secThreatBadge").textContent = `${d.threat_count} Threats`;
      $("#secThreatBadge").className = `s1-badge ${d.threat_count === 0 ? "ok" : "err"}`;
    }
    if (d.threat_count > 0) {
      setOverviewAlert(`🚨 ${d.threat_count} Security Threat(s) Detected!`, "err");
    }
    if ($("#secTotalSockets")) $("#secTotalSockets").textContent = d.total_active_sockets || 0;

    // DNS Leak
    const dns = d.dns || {};
    if ($("#secDnsStatus")) $("#secDnsStatus").textContent = dns.is_encrypted_upstream ? "Encrypted" : "Standard";
    if ($("#secDnsBadge")) {
      $("#secDnsBadge").textContent = dns.is_encrypted_upstream ? "Secure" : "Standard ISP";
      $("#secDnsBadge").className = `s1-badge ${dns.is_encrypted_upstream ? "ok" : "warn"}`;
    }
    if ($("#secDnsRec")) $("#secDnsRec").textContent = dns.recommendation || "";

    const dnsList = $("#secDnsList");
    if (dnsList) {
      const servers = dns.dns_servers || [];
      if (!servers.length) {
        dnsList.innerHTML = '<span class="muted">No upstream DNS configured</span>';
      } else {
        dnsList.innerHTML = servers.map(s => `
          <div class="s1-item ${s.secure ? "appeared" : ""}">
            <span class="s1-sev"></span>
            <span class="s1-msg"><b>${esc(s.ip)}</b> · ${esc(s.provider)}</span>
            <span class="s1-th">${s.secure ? "Secure" : "ISP"}</span>
          </div>
        `).join("");
      }
    }

    // Threats list
    const tList = $("#secThreatList");
    if (tList) {
      const threats = d.threats || [];
      if (!threats.length) {
        tList.innerHTML = '<div class="s1-item" style="justify-content:center"><span class="muted">All clear — no insecure ports or active threats detected</span></div>';
      } else {
        tList.innerHTML = threats.map(t => `
          <div class="s1-item ${t.severity === "critical" ? "critical" : "warning"}">
            <span class="s1-sev"></span>
            <span class="s1-msg"><b>${esc(t.title)}</b> — ${esc(t.description)}</span>
            <span class="s1-th">${esc(t.process)}</span>
          </div>
        `).join("");
      }
    }
  } catch (e) {
    console.error("Security audit error:", e);
  } finally {
    if (btn) btn.textContent = "🛡️ Run Threat Audit";
  }
}

$("#runSecAuditBtn")?.addEventListener("click", () => loadSecurityAudit());

async function doWhoisLookup() {
  const ip = ($("#whoisInput")?.value || "").trim();
  const box = $("#whoisResult");
  if (!box) return;
  if (!ip) {
    box.innerHTML = '<span style="color:var(--err)">Please enter an IP address</span>';
    return;
  }
  box.innerHTML = '<span class="muted">Querying WHOIS & ASN records…</span>';
  try {
    const res = await api(`/api/security/whois?ip=${encodeURIComponent(ip)}`);
    if (res.error) {
      box.innerHTML = `<span style="color:var(--err)">${esc(res.error)}</span>`;
      return;
    }
    box.innerHTML = `
      <div style="background:#0e172a;border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-top:6px">
        <div style="font-weight:700;color:#38bdf8;margin-bottom:4px">${esc(res.ip)} · ${esc(res.city)}, ${esc(res.country)}</div>
        <div><span class="muted">Organization:</span> <b>${esc(res.org || res.isp)}</b></div>
        <div><span class="muted">ASN:</span> <span class="mono">${esc(res.asn)}</span></div>
        <div><span class="muted">Timezone:</span> ${esc(res.timezone)}</div>
        <div style="margin-top:4px"><span class="badge ${res.is_hosting ? "b-est" : "b-dev"}">${res.is_hosting ? "Cloud / Datacenter" : "Residential / ISP"}</span></div>
      </div>
    `;
  } catch (e) {
    box.innerHTML = `<span style="color:var(--err)">Lookup failed</span>`;
  }
}

async function doThreatIntelLookup() {
  const ip = $("#whoisInput")?.value?.trim();
  const box = $("#whoisResult");
  if (!box) return;
  if (!ip) {
    box.innerHTML = '<span style="color:var(--err)">Please enter an IP address</span>';
    return;
  }
  box.innerHTML = '<span class="muted">Querying AlienVault OTX Threat Intelligence…</span>';
  try {
    const res = await api(`/api/security/threat-intel?ip=${encodeURIComponent(ip)}`);
    if (res.error) {
      box.innerHTML = `<span style="color:var(--err)">${esc(res.error)}</span>`;
      return;
    }
    box.innerHTML = `
      <div style="background:#0e172a;border:1px solid ${res.safe ? 'var(--ok)' : 'var(--err)'};border-radius:8px;padding:10px 12px;margin-top:6px">
        <div style="font-weight:700;color:${res.safe ? 'var(--ok)' : 'var(--err)'};margin-bottom:4px">
          ${res.safe ? "✅ SAFE: No threats detected" : "⚠️ MALICIOUS: " + res.threats + " threat reports found!"}
        </div>
        <div><span class="muted">IP:</span> <b>${esc(res.ip)}</b></div>
        ${!res.safe ? `<div><span class="muted">Recent threat signatures:</span> <b style="color:var(--err)">${esc(res.pulse_names.join(", "))}</b></div>` : ""}
        <div style="margin-top:4px"><span class="badge ${res.safe ? "b-est" : "b-no"}">${res.safe ? "Clean Reputation" : "High Risk"}</span></div>
      </div>
    `;
  } catch (e) {
    box.innerHTML = `<span style="color:var(--err)">Lookup failed</span>`;
  }
}

$("#whoisBtn")?.addEventListener("click", doWhoisLookup);
$("#threatIntelBtn")?.addEventListener("click", doThreatIntelLookup);
$("#whoisInput")?.addEventListener("keydown", (e) => { if (e.key === "Enter") doWhoisLookup(); });

/* ---------- speed test & qos ---------- */
let speedPoller = null;

function setGaugeNeedle(mbps, maxExpected = 200) {
  const fill = $("#speedGaugeFill");
  if (!fill) return;
  const ratio = Math.min(1, Math.max(0, mbps / maxExpected));
  // circumference arc is ~377
  const offset = 377 - (ratio * 377);
  fill.style.strokeDashoffset = offset;
}

async function startSpeedTest() {
  const btn = $("#startSpeedtestBtn");
  if (btn) btn.disabled = true;
  const bar = $("#speedProgressBar"), pfill = $("#speedProgressFill");
  if (bar) bar.hidden = false;

  try {
    await api("/api/speedtest/start");
    if (speedPoller) clearInterval(speedPoller);

    speedPoller = setInterval(async () => {
      try {
        const st = await api("/api/speedtest/status");
        if (pfill) pfill.style.width = (st.progress || 0) + "%";
        if ($("#speedGaugeStage")) $("#speedGaugeStage").textContent = st.stage || "Testing";

        if (st.stage === "ping") {
          if ($("#speedGaugeText")) $("#speedGaugeText").textContent = (st.ping_ms || 0).toFixed(1);
          if ($("#speedGaugeUnit")) $("#speedGaugeUnit").textContent = "ms (Ping)";
        } else if (st.stage === "download") {
          const dl = st.download_mbps || 0;
          if ($("#speedGaugeText")) $("#speedGaugeText").textContent = dl.toFixed(1);
          if ($("#speedGaugeUnit")) $("#speedGaugeUnit").textContent = "Mbps (Down)";
          setGaugeNeedle(dl, 300);
        } else if (st.stage === "upload") {
          const up = st.upload_mbps || 0;
          if ($("#speedGaugeText")) $("#speedGaugeText").textContent = up.toFixed(1);
          if ($("#speedGaugeUnit")) $("#speedGaugeUnit").textContent = "Mbps (Up)";
          setGaugeNeedle(up, 100);
        }

        if ($("#spDownload")) $("#spDownload").textContent = st.download_mbps ? st.download_mbps + " Mbps" : "—";
        if ($("#spUpload")) $("#spUpload").textContent = st.upload_mbps ? st.upload_mbps + " Mbps" : "—";
        if ($("#spPing")) $("#spPing").textContent = st.ping_ms ? st.ping_ms + " ms" : "—";
        if ($("#spJitter")) $("#spJitter").textContent = st.jitter_ms ? st.jitter_ms + " ms" : "—";
        if ($("#spLoss")) $("#spLoss").textContent = (st.packet_loss_pct || 0) + "% packet loss";

        if (!st.running && st.stage === "done") {
          clearInterval(speedPoller);
          speedPoller = null;
          if (btn) btn.disabled = false;
          if ($("#speedGaugeStage")) $("#speedGaugeStage").textContent = "Completed ✅";
          setTimeout(() => { if (bar) bar.hidden = true; }, 1500);
        } else if (!st.running && st.stage === "error") {
          clearInterval(speedPoller);
          speedPoller = null;
          if (btn) btn.disabled = false;
          if ($("#speedGaugeStage")) $("#speedGaugeStage").textContent = "Error ❌";
        }
      } catch (e) {
        clearInterval(speedPoller);
        speedPoller = null;
        if (btn) btn.disabled = false;
      }
    }, 250);

  } catch (e) {
    if (btn) btn.disabled = false;
  }
}

$("#startSpeedtestBtn")?.addEventListener("click", startSpeedTest);

/* ---------- wifi analyzer ---------- */
async function loadWifi() {
  const btn = $("#scanWifiBtn");
  if (btn) btn.textContent = "📶 Scanning…";
  try {
    const d = await api("/api/wifi");
    const conn = d.connected;
    const connBox = $("#wifiConnectedDetails");
    const badge = $("#wifiStatusBadge");

    if (!d.has_wifi) {
      if (badge) { badge.textContent = "No Wi-Fi Adapter"; badge.className = "s1-badge warn"; }
      if (connBox) connBox.innerHTML = '<span class="muted">No active wireless adapter detected on this system.</span>';
    } else if (conn) {
      if (badge) { badge.textContent = "Connected"; badge.className = "s1-badge ok"; }
      if (connBox) {
        connBox.innerHTML = `
          <div class="s1-item appeared"><span class="s1-sev"></span><span class="s1-msg">SSID: <b>${esc(conn.ssid)}</b></span><span class="s1-th">${conn.signal_pct}% (${conn.signal_dbm} dBm)</span></div>
          <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">Channel: <b>${conn.channel}</b> (${conn.channel > 14 ? "5 GHz" : "2.4 GHz"})</span><span class="s1-th">${esc(conn.radio_type)}</span></div>
          <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">Security: <b>${esc(conn.authentication)}</b></span><span class="s1-th">Link ${conn.rx_rate_mbps} / ${conn.tx_rate_mbps} Mbps</span></div>
        `;
      }
    } else {
      if (badge) { badge.textContent = "Disconnected"; badge.className = "s1-badge warn"; }
      if (connBox) connBox.innerHTML = '<span class="muted">Wi-Fi adapter is enabled but not connected to any network.</span>';
    }

    // Channel Advisor
    const rec = d.recommendation || {};
    if ($("#wifiAdvisorTip")) $("#wifiAdvisorTip").textContent = rec.tip || "Spectrum analysis complete.";
    if ($("#wifiBest24")) $("#wifiBest24").textContent = rec.best_24_channel != null ? `Ch ${rec.best_24_channel}` : "—";
    if ($("#wifiBest5")) $("#wifiBest5").textContent = rec.best_5_channel != null ? `Ch ${rec.best_5_channel}` : "—";

    // 2.4 GHz Bars
    const b24 = $("#wifiBars24");
    if (b24) {
      const c24 = d.channel_congestion_24 || [];
      const max24 = Math.max(1, ...c24.map(c => c.count));
      b24.innerHTML = c24.map(c => {
        const hgt = Math.max(8, (c.count / max24) * 100);
        const tip = `Ch ${c.channel}: ${c.count} network(s)`;
        return `<div class="s1-bar" style="height:${hgt}%" title="${tip}"><span>${tip}</span></div>`;
      }).join("");
    }

    // 5 GHz Bars
    const b5 = $("#wifiBars5");
    if (b5) {
      const c5 = d.channel_congestion_5 || [];
      const max5 = Math.max(1, ...c5.map(c => c.count));
      b5.innerHTML = c5.map(c => {
        const hgt = Math.max(8, (c.count / max5) * 100);
        const tip = `Ch ${c.channel}: ${c.count} network(s)`;
        return `<div class="s1-bar" style="height:${hgt}%" title="${tip}"><span>${tip}</span></div>`;
      }).join("");
    }

    // Nearby APs Table
    const tb = $("#wifiTableBody");
    const nearby = d.nearby || [];
    if ($("#wifiNearbyCount")) $("#wifiNearbyCount").textContent = `${nearby.length} access point(s)`;
    if (tb) {
      if (!nearby.length) {
        tb.innerHTML = '<tr><td colspan="7" class="muted" style="text-align:center;padding:20px">No nearby wireless networks detected.</td></tr>';
      } else {
        tb.innerHTML = nearby.map(ap => `
          <tr>
            <td><b>${esc(ap.ssid)}</b></td>
            <td><span class="badge ${ap.signal_pct >= 70 ? "b-est" : "b-dev"}">${ap.signal_pct}%</span> <small class="muted">(${ap.signal_dbm} dBm)</small></td>
            <td><span class="mono">Ch ${ap.channel}</span></td>
            <td>${esc(ap.band)}</td>
            <td>${esc(ap.auth)}</td>
            <td><small class="muted">${esc(ap.radio || "—")}</small></td>
            <td><span class="mono" style="font-size:11px">${esc(ap.bssid)}</span></td>
          </tr>
        `).join("");
      }
    }

  } catch (e) {
    console.error("Wi-Fi error:", e);
  } finally {
    if (btn) btn.textContent = "📶 Rescan Wireless";
  }
}

$("#scanWifiBtn")?.addEventListener("click", () => loadWifi());

function openHealthReportModal() {
  const modal = $("#healthModal");
  if (!modal) return;
  modal.hidden = false;
  modal.classList.add("active");
}

function closeHealthReportModal() {
  const modal = $("#healthModal");
  if (!modal) return;
  modal.classList.remove("active");
  modal.hidden = true;
}

/* ---------- health audit report ---------- */
async function generateHealthReport() {
  const area = $("#healthReportPrintArea");
  openHealthReportModal();
  if (!area) return;
  area.innerHTML = '<div style="padding:40px;text-align:center" class="muted">Compiling network intelligence report…</div>';

  try {
    const [summ, sec, topo, conns, ifaces] = await Promise.all([
      api("/api/summary"),
      api("/api/security/audit"),
      api("/api/topology"),
      api("/api/connections"),
      api("/api/interfaces")
    ]);

    const dateStr = new Date().toLocaleString();
    const threats = sec.threats || [];
    const devices = topo.nodes || [];

    area.innerHTML = `
      <div class="rep-header">
        <div>
          <h1 style="font-size:22px;margin-bottom:4px">Network Intelligence & Health Audit</h1>
          <div class="muted">Generated on ${dateStr} · Host: <b>${esc(summ.hostname || "Local PC")}</b> (${esc(summ.primary_ip || "—")})</div>
          <div class="muted">Gateway: <b>${esc(summ.gateway_ip || "—")}</b> (${summ.gateway_up ? "Online" : "Offline"})</div>
        </div>
        <div class="rep-score-box">
          <div class="rep-score-val">${sec.grade || "A+"}</div>
          <div class="muted">Health Score: ${sec.score}/100</div>
        </div>
      </div>

      <div class="rep-section">
        <h3>1. Executive Security & Posture Summary</h3>
        <p>Overall network posture is evaluated at <b>${sec.grade} (${sec.score}/100)</b> with <b>${threats.length}</b> active socket vulnerabilities. DNS resolver configuration is <b>${sec.dns?.is_encrypted_upstream ? "Encrypted (Secure)" : "Standard ISP"}</b>.</p>
        ${threats.length ? `
          <div style="background:#2b1216;border:1px solid #4d2029;border-radius:8px;padding:12px;margin-top:8px">
            <b>Identified Threats:</b>
            <ul style="margin:6px 0 0 18px">
              ${threats.map(t => `<li><b>${esc(t.title)}</b>: ${esc(t.description)}</li>`).join("")}
            </ul>
          </div>
        ` : `<div style="color:var(--ok);margin-top:6px">✅ Zero anomalous or risky ports currently open.</div>`}
      </div>

      <div class="rep-section">
        <h3>2. Discovered Network Inventory</h3>
        <p>Total discovered hosts on primary subnet: <b>${devices.length}</b></p>
        <table class="tbl" style="margin-top:8px">
          <thead><tr><th>IP Address</th><th>Kind</th><th>MAC / Vendor</th><th>Status</th></tr></thead>
          <tbody>
            ${devices.map(d => `
              <tr>
                <td><b>${esc(d.ip)}</b></td>
                <td>${esc(d.kind)}</td>
                <td>${esc(d.vendor || d.mac || "—")}</td>
                <td><span class="badge ${d.status === "up" ? "b-est" : "b-dev"}">${d.status}</span></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>

      <div class="rep-section">
        <h3>3. Active Socket & Network Interface Summary</h3>
        <p>Active connections: <b>${conns.connections?.length || 0}</b> total (<b>${summ.tcp_established || 0}</b> established TCP sockets).</p>
        <p class="muted">Physical Network Interfaces: ${(ifaces.interfaces || []).map(i => `${i.name} (${i.status})`).join(", ") || "Active"}</p>
      </div>
    `;

  } catch (e) {
    area.innerHTML = '<div style="color:var(--err);padding:20px">Failed to compile report.</div>';
  }
}

$("#healthReportBtn")?.addEventListener("click", generateHealthReport);
$("#closeReportBtn")?.addEventListener("click", closeHealthReportModal);
$("#healthModal")?.addEventListener("click", (e) => {
  if (e.target.id === "healthModal") closeHealthReportModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeHealthReportModal();
});
$("#printReportBtn")?.addEventListener("click", () => window.print());

/* ---------- advanced visual profile suite & network tools ---------- */
let netProfilesData = [];
let currentProfileIdx = 0;
let detectedInterfaces = [];

async function loadNetProfiles() {
  const tabsBar = $("#profileTabsBar"), adapterSel = $("#profAdapterSelect");
  if (!tabsBar) return;
  try {
    const [pRes, ifacesRes] = await Promise.all([
      api("/api/profiles/list"),
      api("/api/interfaces")
    ]);
    netProfilesData = pRes.profiles || [];
    detectedInterfaces = ifacesRes.interfaces || [];

    // Populate Adapter Dropdown
    if (adapterSel) {
      adapterSel.innerHTML = detectedInterfaces.map(i => `
        <option value="${esc(i.name)}">${esc(i.name)} (${i.ip || "No IP"}${i.media_down ? " · Down" : ""})</option>
      `).join("") || '<option value="Ethernet">Ethernet</option><option value="Wi-Fi">Wi-Fi</option>';
    }

    renderProfileTabs();
    renderActiveProfile();
  } catch (e) {
    console.error("NetProfiles load error:", e);
  }
}

function renderProfileTabs() {
  const tabsBar = $("#profileTabsBar");
  if (!tabsBar) return;
  if (!netProfilesData.length) {
    createNewProfileTab();
    return;
  }
  if (currentProfileIdx >= netProfilesData.length) currentProfileIdx = 0;

  tabsBar.innerHTML = netProfilesData.map((p, idx) => `
    <button class="prof-tab-btn ${idx === currentProfileIdx ? "active" : ""}" onclick="selectProfileTab(${idx})">
      <span>${p.icon || "📁"} ${esc(p.name)}</span>
      ${netProfilesData.length > 1 ? `<span class="prof-tab-close" onclick="event.stopPropagation();deleteProfileByIndex(${idx})" title="Delete Profile">✕</span>` : ""}
    </button>
  `).join("");
}

window.selectProfileTab = function(idx) {
  currentProfileIdx = idx;
  renderProfileTabs();
  renderActiveProfile();
};

function renderActiveProfile() {
  const p = netProfilesData[currentProfileIdx];
  if (!p) return;

  const nameIn = $("#profNameInput");
  const adapterSel = $("#profAdapterSelect");
  const iconSel = $("#profIconSelect");
  const notesIn = $("#profNotesInput");
  const ipDhcp = $("#profIpRadioDhcp"), ipStatic = $("#profIpRadioStatic");
  const ipAddrIn = $("#profIpAddrInput"), maskIn = $("#profMaskInput"), gwIn = $("#profGwInput");
  const dnsDhcp = $("#profDnsRadioDhcp"), dnsManual = $("#profDnsRadioManual");
  const priDnsIn = $("#profPrimaryDnsInput"), secDnsIn = $("#profSecondaryDnsInput");
  const proxyChk = $("#profProxyChk"), proxyIn = $("#profProxyInput");
  const summaryBox = $("#profSummaryBox"), applyBox = $("#profApplyResultBox");

  if (nameIn) nameIn.value = p.name || `Profile #${currentProfileIdx + 1}`;
  if (iconSel) iconSel.value = p.icon || "🏠";
  if (notesIn) notesIn.value = p.notes || "";
  if (adapterSel && p.adapter) adapterSel.value = p.adapter;

  // IP Config
  const isStaticIp = (p.ip_mode === "static");
  if (ipDhcp && ipStatic) {
    ipDhcp.checked = !isStaticIp;
    ipStatic.checked = isStaticIp;
  }
  if (ipAddrIn) ipAddrIn.value = p.ip_address || "";
  if (maskIn) maskIn.value = p.subnet_mask || "255.255.255.0";
  if (gwIn) gwIn.value = p.gateway || "";
  toggleIpFields(isStaticIp);

  // DNS Config
  const isManualDns = (p.dns_mode === "manual");
  if (dnsDhcp && dnsManual) {
    dnsDhcp.checked = !isManualDns;
    dnsManual.checked = isManualDns;
  }
  if (priDnsIn) priDnsIn.value = p.primary_dns || "";
  if (secDnsIn) secDnsIn.value = p.secondary_dns || "";
  toggleDnsFields(isManualDns);

  // Proxy Config
  if (proxyChk) proxyChk.checked = !!p.proxy_enabled;
  if (proxyIn) proxyIn.value = p.proxy_server || "";
  toggleProxyFields(!!p.proxy_enabled);

  if (applyBox) applyBox.hidden = true;
  if (summaryBox) {
    summaryBox.innerHTML = `
      <div><b>Adapter:</b> ${esc(p.adapter || "Default Active Interface")}</div>
      <div><b>IP Mode:</b> ${isStaticIp ? `Static IP (${esc(p.ip_address || "None")})` : "Automatic DHCP"}</div>
      <div><b>DNS:</b> ${isManualDns ? `Manual (${esc(p.primary_dns || "None")}${p.secondary_dns ? ", " + p.secondary_dns : ""})` : "Automatic DHCP"}</div>
      ${p.notes ? `<div class="muted" style="margin-top:4px">${esc(p.notes)}</div>` : ""}
    `;
  }
}

function toggleIpFields(isStatic) {
  const box = $("#profStaticFields");
  if (box) {
    box.style.opacity = isStatic ? "1" : "0.35";
    box.style.pointerEvents = isStatic ? "auto" : "none";
  }
}
function toggleDnsFields(isManual) {
  const box = $("#profManualDnsFields");
  if (box) {
    box.style.opacity = isManual ? "1" : "0.35";
    box.style.pointerEvents = isManual ? "auto" : "none";
  }
}
function toggleProxyFields(isEnabled) {
  const box = $("#profProxyFields");
  if (box) {
    box.style.opacity = isEnabled ? "1" : "0.35";
    box.style.pointerEvents = isEnabled ? "auto" : "none";
  }
}

$("#profIpRadioDhcp")?.addEventListener("change", () => toggleIpFields(false));
$("#profIpRadioStatic")?.addEventListener("change", () => toggleIpFields(true));
$("#profDnsRadioDhcp")?.addEventListener("change", () => toggleDnsFields(false));
$("#profDnsRadioManual")?.addEventListener("change", () => toggleDnsFields(true));
$("#profProxyChk")?.addEventListener("change", (e) => toggleProxyFields(e.target.checked));

window.fillProfileDns = function(primary, secondary) {
  const dnsManual = $("#profDnsRadioManual");
  if (dnsManual) dnsManual.checked = true;
  toggleDnsFields(true);
  const pri = $("#profPrimaryDnsInput"), sec = $("#profSecondaryDnsInput");
  if (pri) pri.value = primary;
  if (sec) sec.value = secondary;
};

function getFormData() {
  const p = netProfilesData[currentProfileIdx] || {};
  return {
    id: p.id || `p_${Date.now()}`,
    name: $("#profNameInput")?.value.trim() || `Profile #${currentProfileIdx + 1}`,
    adapter: $("#profAdapterSelect")?.value || "",
    icon: $("#profIconSelect")?.value || "📁",
    notes: $("#profNotesInput")?.value.trim() || "",
    ip_mode: $("#profIpRadioStatic")?.checked ? "static" : "dhcp",
    ip_address: $("#profIpAddrInput")?.value.trim() || "",
    subnet_mask: $("#profMaskInput")?.value.trim() || "255.255.255.0",
    gateway: $("#profGwInput")?.value.trim() || "",
    dns_mode: $("#profDnsRadioManual")?.checked ? "manual" : "dhcp",
    primary_dns: $("#profPrimaryDnsInput")?.value.trim() || "",
    secondary_dns: $("#profSecondaryDnsInput")?.value.trim() || "",
    proxy_enabled: !!$("#profProxyChk")?.checked,
    proxy_server: $("#profProxyInput")?.value.trim() || "",
    created_at: p.created_at || Date.now() / 1000
  };
}

async function saveCurrentProfile(silent) {
  const data = getFormData();
  netProfilesData[currentProfileIdx] = data;
  try {
    const r = await fetch("/api/profiles/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    const res = await r.json();
    if (res.ok) {
      if (!silent) {
        const fb = $("#profSaveFeedback");
        if (fb) {
          fb.textContent = "✅ Profile Saved!";
          setTimeout(() => { if (fb) fb.textContent = ""; }, 3000);
        }
      }
      renderProfileTabs();
      renderActiveProfile();
    }
  } catch (e) {
    if (!silent) alert("Error saving profile: " + e.message);
  }
}

async function applyCurrentProfile() {
  await saveCurrentProfile(true);
  const p = netProfilesData[currentProfileIdx];
  if (!p) return;
  const btn = $("#profApplyBtn"), resultBox = $("#profApplyResultBox");
  if (btn) { btn.disabled = true; btn.textContent = "⚡ Applying Profile…"; }
  if (resultBox) { resultBox.hidden = false; resultBox.innerHTML = '<span class="muted">Configuring network adapter, IP & DNS…</span>'; }

  try {
    const res = await api(`/api/profiles/apply?id=${encodeURIComponent(p.id)}`);
    if (resultBox) {
      const steps = res.steps || [];
      resultBox.innerHTML = `
        <div style="font-weight:700;margin-bottom:6px;color:var(--ok)">${esc(res.summary)}</div>
        ${steps.map(s => `
          <div style="font-size:11.5px;color:${s.ok ? "var(--ok)" : "var(--err)"}">
            ${s.ok ? "✔" : "✖"} ${esc(s.action)}: ${esc(s.output || "OK")}
          </div>
        `).join("")}
      `;
    }
    loadOverview();
    loadInterfaces();
  } catch (e) {
    if (resultBox) resultBox.innerHTML = `<span class="err">Apply Error: ${esc(e.message)}</span>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "⚡ Apply Profile Now"; }
  }
}

function createNewProfileTab() {
  const newProf = {
    id: `p_${Date.now()}`,
    name: `#${netProfilesData.length + 1} New Profile`,
    adapter: detectedInterfaces[0]?.name || "",
    ip_mode: "dhcp",
    ip_address: "",
    subnet_mask: "255.255.255.0",
    gateway: "",
    dns_mode: "dhcp",
    primary_dns: "",
    secondary_dns: "",
    proxy_enabled: false,
    proxy_server: "",
    notes: "",
    icon: "📁",
    created_at: Date.now() / 1000
  };
  netProfilesData.push(newProf);
  currentProfileIdx = netProfilesData.length - 1;
  saveCurrentProfile(true);
}

function duplicateCurrentProfile() {
  const cur = netProfilesData[currentProfileIdx];
  if (!cur) return;
  const clone = JSON.parse(JSON.stringify(cur));
  clone.id = `p_${Date.now()}`;
  clone.name = `${cur.name} (Copy)`;
  netProfilesData.push(clone);
  currentProfileIdx = netProfilesData.length - 1;
  saveCurrentProfile(true);
}

window.deleteProfileByIndex = async function(idx) {
  if (netProfilesData.length <= 1) {
    alert("Cannot delete the only remaining profile.");
    return;
  }
  const p = netProfilesData[idx];
  if (!confirm(`Are you sure you want to delete profile "${p.name}"?`)) return;
  try {
    await api(`/api/profiles/delete?id=${encodeURIComponent(p.id)}`);
    netProfilesData.splice(idx, 1);
    if (currentProfileIdx >= netProfilesData.length) currentProfileIdx = netProfilesData.length - 1;
    renderProfileTabs();
    renderActiveProfile();
  } catch (e) {
    alert("Delete error: " + e.message);
  }
};

$("#profNewTabBtn")?.addEventListener("click", createNewProfileTab);
$("#profSaveBtn")?.addEventListener("click", () => saveCurrentProfile(false));
$("#profApplyBtn")?.addEventListener("click", applyCurrentProfile);
$("#profDuplicateBtn")?.addEventListener("click", duplicateCurrentProfile);
$("#profDeleteBtn")?.addEventListener("click", () => deleteProfileByIndex(currentProfileIdx));

/* ---------- tools tab: dns switcher & quick repair ---------- */
async function loadDnsPresets() {
  const grid = $("#dnsPresetsGrid"), adEl = $("#dnsActiveAdapter");
  if (!grid) return;
  try {
    const d = await api("/api/profiles/dns-presets");
    if (adEl) adEl.textContent = `Active Adapter: ${d.adapter || "Default"}`;
    const presets = d.presets || [];
    grid.innerHTML = presets.map(p => `
      <div class="dns-preset-card" data-id="${p.id}">
        <div class="dns-card-head">
          <span class="dns-card-title">${p.icon} ${esc(p.name)}</span>
          <span class="badge ${p.id === "dhcp" ? "b-dev" : "b-est"}">${p.tag}</span>
        </div>
        <div class="dns-card-ips">${p.primary}${p.secondary ? " · " + p.secondary : ""}</div>
        <div class="dns-card-desc">${esc(p.desc)}</div>
        <button class="btn btn-accent dns-card-apply-btn" onclick="applyDnsPreset('${p.id}')">Apply DNS</button>
      </div>
    `).join("");
  } catch (e) {
    console.error("DNS presets error:", e);
  }
}

window.applyDnsPreset = async function(presetId) {
  const log = $("#dnsApplyLog");
  if (log) { log.hidden = false; log.textContent = `Applying DNS preset '${presetId}'…`; }
  try {
    const r = await api(`/api/profiles/set-dns?preset=${encodeURIComponent(presetId)}`);
    if (log) {
      log.textContent = r.ok ? `✅ Applied ${presetId} successfully!` : `⚠️ ${r.output || r.error || "Failed"}`;
      setTimeout(() => { if (log) log.hidden = true; }, 4000);
    }
    loadOverview();
    loadSecurityAudit();
  } catch (e) {
    if (log) log.textContent = `❌ Error: ${e.message}`;
  }
};

async function runQuickRepair() {
  const btn = $("#quickRepairBtn"), card = $("#repairLogCard"), list = $("#repairStepList");
  if (btn) { btn.disabled = true; btn.textContent = "⚙️ Repairing Network…"; }
  if (card) card.hidden = false;
  if (list) list.innerHTML = '<div class="s1-item"><span class="muted">Running ipconfig /flushdns, purging ARP cache, and re-registering network endpoints…</span></div>';

  try {
    const r = await api("/api/profiles/repair");
    if (list) {
      list.innerHTML = (r.steps || []).map(s => `
        <div class="s1-item ${s.ok ? "appeared" : "critical"}">
          <span class="s1-sev"></span>
          <span class="s1-msg"><b>${esc(s.step)}</b></span>
          <span class="s1-th">${s.ok ? "SUCCESS" : "FAILED"}</span>
        </div>
      `).join("") + `<div style="color:var(--ok);font-weight:600;margin-top:8px">${esc(r.summary)}</div>`;
    }
    loadOverview();
  } catch (e) {
    if (list) list.innerHTML = `<div style="color:var(--err)">Repair failed: ${esc(e.message)}</div>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "⚡ 1-Click Network Repair & Flush"; }
  }
}

async function sendWolMagicPacket() {
  const macIn = $("#wolMacInput"), st = $("#wolStatus");
  const mac = macIn ? macIn.value.trim() : "";
  if (!mac) {
    if (st) st.textContent = "Please enter a valid MAC address.";
    return;
  }
  if (st) st.textContent = "Transmitting Magic Packet broadcast…";
  try {
    const r = await api(`/api/profiles/wol?mac=${encodeURIComponent(mac)}`);
    if (st) {
      st.textContent = r.ok ? `✅ ${r.msg}` : `❌ ${r.error || "Failed"}`;
      st.style.color = r.ok ? "var(--ok)" : "var(--err)";
    }
  } catch (e) {
    if (st) st.textContent = `❌ Error: ${e.message}`;
  }
}

window.triggerWolFromDevice = function(mac) {
  const tabBtn = document.querySelector('[data-tab="nettools"]');
  if (tabBtn) tabBtn.click();
  const macIn = $("#wolMacInput");
  if (macIn) { macIn.value = mac; }
  sendWolMagicPacket();
};

$("#quickRepairBtn")?.addEventListener("click", runQuickRepair);
$("#sendWolBtn")?.addEventListener("click", sendWolMagicPacket);

/* ---------- advanced live packet sniffer ---------- */
let snifferTimer = null;
let snifferActive = false;
let currentPackets = [];
let selectedPacketId = null;

function getProtoPillClass(proto) {
  const p = (proto || "").toUpperCase();
  if (p.includes("DNS") || p.includes("DOT")) return "dns";
  if (p.includes("TLS") || p.includes("HTTPS")) return "tls";
  if (p.includes("HTTP")) return "http";
  if (p.includes("TCP")) return "tcp";
  if (p.includes("UDP") || p.includes("QUIC")) return "udp";
  if (p.includes("ICMP")) return "icmp";
  return "tcp";
}

async function fetchSnifferData() {
  const proto = $("#sniffProtoFilter") ? $("#sniffProtoFilter").value : "ALL";
  const search = $("#sniffSearchInput") ? $("#sniffSearchInput").value.trim() : "";

  try {
    const [pData, sData] = await Promise.all([
      api(`/api/sniffer/packets?limit=120&proto=${encodeURIComponent(proto)}&search=${encodeURIComponent(search)}`),
      api("/api/sniffer/status")
    ]);

    currentPackets = pData.packets || [];
    renderSniffTable(currentPackets);

    // Update counter
    const cEl = $("#sniffCounter");
    if (cEl) cEl.textContent = `${sData.total_captured || 0} captured · ${sData.buffered || 0} in buffer (${snifferActive ? "▶ RUNNING" : "⏸ PAUSED"})`;

    // Update protocol distribution bar
    renderProtoDist(sData.proto_distribution || {});

  } catch (e) {
    console.error("Sniffer poll error:", e);
  }
}

function renderProtoDist(dist) {
  const bar = $("#sniffProtoBar");
  if (!bar) return;
  const entries = Object.entries(dist);
  if (!entries.length) {
    bar.innerHTML = '<span class="muted" style="font-size:12px">No protocol telemetry sampled yet.</span>';
    return;
  }
  const total = entries.reduce((a, b) => a + b[1], 0) || 1;
  bar.innerHTML = entries.map(([p, cnt]) => {
    const pct = Math.round((cnt / total) * 100);
    const cls = getProtoPillClass(p);
    return `<span class="sniff-proto-pill ${cls}"><b>${esc(p)}</b>: ${cnt} <small>(${pct}%)</small></span>`;
  }).join("");
}

function renderSniffTable(list) {
  const tb = $("#sniffTableBody");
  if (!tb) return;
  if (!list.length) {
    tb.innerHTML = `<tr><td colspan="8" class="muted" style="text-align:center;padding:30px">${snifferActive ? "Capturing live packets…" : "No packets in buffer. Click <b>▶ Start Capture</b>."}</td></tr>`;
    return;
  }

  tb.innerHTML = list.map(p => {
    const isSel = (p.id === selectedPacketId);
    const cls = getProtoPillClass(p.protocol);
    return `
      <tr class="row-cls-${cls} ${isSel ? "selected" : ""}" onclick="selectPacketRow(${p.id})">
        <td class="mono" style="color:var(--faint)">${p.id}</td>
        <td class="mono" style="font-size:11.5px">${p.time_str}</td>
        <td class="mono"><b>${esc(p.src)}</b>${p.sport ? `<small class="muted">:${p.sport}</small>` : ""}</td>
        <td class="mono"><b>${esc(p.dst)}</b>${p.dport ? `<small class="muted">:${p.dport}</small>` : ""}</td>
        <td><span class="sniff-proto-pill ${cls}" style="padding:1px 6px;font-size:11px">${esc(p.protocol)}</span></td>
        <td class="mono">${p.len} B</td>
        <td style="font-size:12px;color:var(--txt)">${esc(p.info)}</td>
        <td>
          ${p.sport && p.dport ? `<button class="btn" style="padding:2px 6px;font-size:10.5px;color:var(--accent)" onclick="event.stopPropagation();followStream('${p.src}',${p.sport},'${p.dst}',${p.dport})">🌊 Follow</button>` : `<span class="muted">—</span>`}
        </td>
      </tr>
    `;
  }).join("");
}

window.selectPacketRow = function(id) {
  selectedPacketId = id;
  const pkt = currentPackets.find(p => p.id === id);
  if (!pkt) return;

  // Highlight row in table
  $$("#sniffTableBody tr").forEach(tr => tr.classList.remove("selected"));
  const row = $$("#sniffTableBody tr").find(tr => tr.children[0]?.textContent == id);
  if (row) row.classList.add("selected");

  // Show Inspector Box
  const insp = $("#sniffInspector");
  if (!insp) return;
  insp.hidden = false;

  // Header Title & Badges
  if ($("#sniffInspFrameTitle")) $("#sniffInspFrameTitle").textContent = `Frame #${pkt.id}`;
  if ($("#sniffInspProtoBadge")) {
    $("#sniffInspProtoBadge").textContent = pkt.protocol;
    $("#sniffInspProtoBadge").className = `badge ${getProtoPillClass(pkt.protocol)}`;
  }
  if ($("#sniffInspEndpoints")) {
    const sPort = pkt.sport ? `:${pkt.sport}` : "";
    const dPort = pkt.dport ? `:${pkt.dport}` : "";
    $("#sniffInspEndpoints").textContent = `${pkt.src}${sPort} ➔ ${pkt.dst}${dPort}`;
  }

  // Render Interactive Collapsible Protocol Dissection Tree
  renderDissectionTree(pkt);

  // Render Synchronized Interactive Hex & ASCII Dump
  renderInteractiveHexDump(pkt);

  // If Deep Intelligence Drawer is active, live-update it!
  const drawerModal = $("#packetDrawerModal");
  if (drawerModal && !drawerModal.hidden && drawerModal.classList.contains("active")) {
    updatePacketDrawerContent(pkt);
  }
};

function renderDissectionTree(pkt) {
  const tree = $("#sniffTreeContent");
  if (!tree) return;
  const d = pkt.dissection || {};
  const f = d.frame || { id: pkt.id, len_bytes: pkt.len, len_bits: pkt.len * 8, time_str: pkt.time_str };
  const ip = d.ipv4 || { version: 4, src: pkt.src, dst: pkt.dst, ttl: pkt.ttl, proto_name: pkt.ip_proto };
  const trans = d.transport || { type: pkt.ip_proto, sport: pkt.sport, dport: pkt.dport };
  const app = d.application || { protocol: pkt.protocol, summary: pkt.info };
  const exp = d.expert_info || { severity: "INFO", group: "General", summary: pkt.info };
  const ranges = d.byte_ranges || { ip: [0, 20], transport: [20, 40], payload: [40, pkt.len] };

  tree.innerHTML = `
    <!-- Layer 1: Frame / Wire -->
    <div class="sniff-layer-card" data-range="0,${pkt.len}" onclick="highlightLayerBytes(0, ${pkt.len}, this)">
      <div class="sniff-layer-head" onclick="toggleLayerAccordion(event, this)">
        <span>🖼️ <b>Frame ${f.id}</b>: ${f.len_bytes} bytes (${f.len_bits} bits) on wire</span>
        <span class="muted" style="font-size:11px">▼</span>
      </div>
      <div class="sniff-layer-fields">
        <div class="sniff-field-row"><span class="k">Arrival Time:</span><span class="v">${f.time_str}</span></div>
        <div class="sniff-field-row"><span class="k">Frame Length:</span><span class="v">${f.len_bytes} bytes (${f.len_bits} bits)</span></div>
        <div class="sniff-field-row"><span class="k">Capture Length:</span><span class="v">${f.len_bytes} bytes</span></div>
      </div>
    </div>

    <!-- Layer 2: Internet Protocol Version 4 -->
    <div class="sniff-layer-card" data-range="${ranges.ip[0]},${ranges.ip[1]}" onclick="highlightLayerBytes(${ranges.ip[0]}, ${ranges.ip[1]}, this)">
      <div class="sniff-layer-head" onclick="toggleLayerAccordion(event, this)">
        <span>🌐 <b>IPv4</b>, Src: ${esc(ip.src)}, Dst: ${esc(ip.dst)}</span>
        <span class="muted" style="font-size:11px">▼</span>
      </div>
      <div class="sniff-layer-fields">
        <div class="sniff-field-row"><span class="k">Source IP:</span><span class="v"><b>${esc(ip.src)}</b></span></div>
        <div class="sniff-field-row"><span class="k">Destination IP:</span><span class="v"><b>${esc(ip.dst)}</b></span></div>
        <div class="sniff-field-row"><span class="k">Time to Live (TTL):</span><span class="v">${ip.ttl} <small class="muted">(${esc(ip.os_guess || "OS Fingerprint")})</small></span></div>
        <div class="sniff-field-row"><span class="k">Header Length (IHL):</span><span class="v">${ip.ihl ? ip.ihl + " bytes" : "20 bytes"}</span></div>
        <div class="sniff-field-row"><span class="k">Flags / Offset:</span><span class="v">DF=${ip.df ? "1" : "0"}, MF=${ip.mf ? "1" : "0"} (Offset ${ip.offset || 0})</span></div>
        <div class="sniff-field-row"><span class="k">Identification:</span><span class="v">${ip.ident || "0x0000"}</span></div>
        <div class="sniff-field-row"><span class="k">Header Checksum:</span><span class="v">${ip.checksum || "—"}</span></div>
      </div>
    </div>

    <!-- Layer 3: Transport Protocol (TCP / UDP / ICMP) -->
    <div class="sniff-layer-card" data-range="${ranges.transport[0]},${ranges.transport[1]}" onclick="highlightLayerBytes(${ranges.transport[0]}, ${ranges.transport[1]}, this)">
      <div class="sniff-layer-head" onclick="toggleLayerAccordion(event, this)">
        <span>⚡ <b>${esc(trans.type)} Protocol</b>, Src Port: ${trans.sport || "—"}, Dst Port: ${trans.dport || "—"}</span>
        <span class="muted" style="font-size:11px">▼</span>
      </div>
      <div class="sniff-layer-fields">
        ${trans.type === "TCP" ? `
          <div class="sniff-field-row"><span class="k">Source Port:</span><span class="v">${trans.sport}</span></div>
          <div class="sniff-field-row"><span class="k">Destination Port:</span><span class="v">${trans.dport}</span></div>
          <div class="sniff-field-row"><span class="k">Sequence Number:</span><span class="v">${trans.seq} (raw)</span></div>
          <div class="sniff-field-row"><span class="k">Acknowledgment:</span><span class="v">${trans.ack} (raw)</span></div>
          <div class="sniff-field-row"><span class="k">Header Length:</span><span class="v">${trans.hdr_len || 20} bytes</span></div>
          <div class="sniff-field-row"><span class="k">Window Size:</span><span class="v">${trans.window || "—"}</span></div>
          <div class="sniff-field-row"><span class="k">Flags Matrix:</span><span class="v" style="display:flex;gap:4px;flex-wrap:wrap">
            ${["SYN", "ACK", "FIN", "RST", "PSH", "URG", "ECE", "CWR"].map(flg => `
              <span class="tcp-flag-badge ${trans.flags?.includes(flg) ? "on" : "off"}">${flg}</span>
            `).join("")}
          </span></div>
          <div class="sniff-field-row"><span class="k">Checksum:</span><span class="v">${trans.checksum || "—"}</span></div>
        ` : trans.type === "UDP" ? `
          <div class="sniff-field-row"><span class="k">Source Port:</span><span class="v">${trans.sport}</span></div>
          <div class="sniff-field-row"><span class="k">Destination Port:</span><span class="v">${trans.dport}</span></div>
          <div class="sniff-field-row"><span class="k">Length:</span><span class="v">${trans.length || 0} bytes</span></div>
          <div class="sniff-field-row"><span class="k">Checksum:</span><span class="v">${trans.checksum || "—"}</span></div>
        ` : `
          <div class="sniff-field-row"><span class="k">ICMP Type:</span><span class="v">${esc(trans.type_name || "Echo")}</span></div>
          <div class="sniff-field-row"><span class="k">Code:</span><span class="v">${trans.icmp_code || 0}</span></div>
          <div class="sniff-field-row"><span class="k">Checksum:</span><span class="v">${trans.checksum || "—"}</span></div>
        `}
      </div>
    </div>

    <!-- Layer 4: Application Layer Payload -->
    <div class="sniff-layer-card" data-range="${ranges.payload[0]},${ranges.payload[1]}" onclick="highlightLayerBytes(${ranges.payload[0]}, ${ranges.payload[1]}, this)">
      <div class="sniff-layer-head" onclick="toggleLayerAccordion(event, this)">
        <span>📦 <b>Application Layer</b>: <span style="color:#34d399">${esc(app.protocol)}</span></span>
        <span class="muted" style="font-size:11px">▼</span>
      </div>
      <div class="sniff-layer-fields">
        <div class="sniff-field-row"><span class="k">Protocol:</span><span class="v"><b>${esc(app.protocol)}</b></span></div>
        <div class="sniff-field-row"><span class="k">Summary:</span><span class="v">${esc(app.summary)}</span></div>
        ${app.details?.sni ? `<div class="sniff-field-row"><span class="k">TLS SNI:</span><span class="v" style="color:var(--accent);font-weight:700">${esc(app.details.sni)}</span></div>` : ""}
        ${app.details?.dns_query ? `<div class="sniff-field-row"><span class="k">DNS Query:</span><span class="v" style="color:var(--accent);font-weight:700">${esc(app.details.dns_query)} (${esc(app.details.dns_type || "A")})</span></div>` : ""}
        ${app.details?.http?.request_line ? `<div class="sniff-field-row"><span class="k">HTTP Request:</span><span class="v" style="color:#facc15;font-weight:700">${esc(app.details.http.request_line)}</span></div>` : ""}
        <div class="sniff-field-row"><span class="k">Payload Length:</span><span class="v">${Math.max(0, pkt.len - ranges.payload[0])} bytes</span></div>
      </div>
    </div>

    <!-- Layer 5: Deep Packet Expert Info & Anomaly Analysis -->
    <div class="sniff-layer-card">
      <div class="sniff-layer-head" style="background:#1c1328;border-bottom:1px solid #3b2054">
        <span>🛡️ <b>Deep Packet Expert Info</b> <span class="badge ${exp.severity === "WARN" ? "badge-risk-high" : exp.severity === "NOTE" ? "badge-risk-medium" : "badge-risk-safe"}" style="padding:1px 6px;font-size:10px">${esc(exp.severity)}</span></span>
        <span class="muted" style="font-size:11px">▼</span>
      </div>
      <div class="sniff-layer-fields" style="background:#0e0a17">
        <div class="sniff-field-row"><span class="k">Category:</span><span class="v"><b>${esc(exp.group)}</b></span></div>
        <div class="sniff-field-row"><span class="k">Analysis:</span><span class="v" style="color:#f1f5f9">${esc(exp.summary)}</span></div>
        <div class="sniff-field-row"><span class="k">Security Note:</span><span class="v" style="color:#94a3b8">${esc(exp.recommendation)}</span></div>
      </div>
    </div>
  `;
}

function toggleLayerAccordion(e, head) {
  e.stopPropagation();
  const card = head.parentElement;
  const fields = card.querySelector(".sniff-layer-fields");
  if (!fields) return;
  const isHidden = (fields.style.display === "none");
  fields.style.display = isHidden ? "flex" : "none";
  const arrow = head.querySelector(".muted");
  if (arrow) arrow.textContent = isHidden ? "▼" : "▶";
}

function highlightLayerBytes(start, end, card) {
  $$(".sniff-layer-card").forEach(c => c.classList.remove("highlighted"));
  if (card) card.classList.add("highlighted");

  const spans = $$("#sniffHexContainer .hex-span");
  spans.forEach(sp => {
    const idx = parseInt(sp.dataset.offset, 10);
    if (idx >= start && idx < end) {
      sp.classList.add("active-layer");
    } else {
      sp.classList.remove("active-layer");
    }
  });

  const layerName = card?.querySelector("b")?.textContent || "Layer";
  const hoverBox = $("#sniffByteHoverInfo");
  if (hoverBox) {
    hoverBox.innerHTML = `<span>Highlighted: <b>${esc(layerName)}</b> (Bytes ${start} to ${end - 1} · Length: ${end - start} bytes)</span>`;
  }
}

function renderInteractiveHexDump(pkt) {
  const hexBox = $("#sniffHexBox");
  if (!hexBox) return;

  const rawHex = pkt.raw_hex || "";
  if (!rawHex) {
    hexBox.textContent = pkt.hex_dump || "(No raw bytes available)";
    return;
  }

  const d = pkt.dissection || {};
  const ranges = d.byte_ranges || { ip: [0, 20], transport: [20, 40], payload: [40, pkt.len] };
  const bytes = [];
  for (let i = 0; i < rawHex.length; i += 2) {
    bytes.push(parseInt(rawHex.substr(i, 2), 16));
  }

  let html = "";
  for (let rowStart = 0; rowStart < bytes.length; rowStart += 16) {
    const rowBytes = bytes.slice(rowStart, rowStart + 16);
    const offsetStr = rowStart.toString(16).padStart(4, "0");
    
    // Hex spans
    let hexSpans = "";
    for (let i = 0; i < 16; i++) {
      const byteIdx = rowStart + i;
      if (i < rowBytes.length) {
        const b = rowBytes[i];
        const hexVal = b.toString(16).padStart(2, "0");
        let layerClass = "";
        let layerName = "Data";
        if (byteIdx >= ranges.ip[0] && byteIdx < ranges.ip[1]) {
          layerClass = "ip-hdr";
          layerName = "IPv4 Header";
        } else if (byteIdx >= ranges.transport[0] && byteIdx < ranges.transport[1]) {
          layerClass = "trans-hdr";
          layerName = `${pkt.ip_proto} Header`;
        } else if (byteIdx >= ranges.payload[0]) {
          layerClass = "payload";
          layerName = `${pkt.protocol} Payload`;
        }

        hexSpans += `<span class="hex-span ${layerClass}" data-offset="${byteIdx}" data-byte="${b}" data-hex="${hexVal}" data-layer="${layerName}" onmouseenter="handleByteHover(this)">${hexVal}</span> `;
      } else {
        hexSpans += "   ";
      }
      if (i === 7) hexSpans += " "; // 8-byte separator
    }

    // ASCII spans
    let asciiSpans = "";
    rowBytes.forEach((b, i) => {
      const byteIdx = rowStart + i;
      const char = (b >= 32 && b <= 126) ? String.fromCharCode(b) : ".";
      let layerClass = "";
      let layerName = "Data";
      if (byteIdx >= ranges.ip[0] && byteIdx < ranges.ip[1]) {
        layerClass = "ip-hdr";
        layerName = "IPv4 Header";
      } else if (byteIdx >= ranges.transport[0] && byteIdx < ranges.transport[1]) {
        layerClass = "trans-hdr";
        layerName = `${pkt.ip_proto} Header`;
      } else if (byteIdx >= ranges.payload[0]) {
        layerClass = "payload";
        layerName = `${pkt.protocol} Payload`;
      }

      asciiSpans += `<span class="hex-span ${layerClass}" data-offset="${byteIdx}" data-byte="${b}" data-layer="${layerName}" onmouseenter="handleByteHover(this)">${esc(char)}</span>`;
    });

    html += `<span class="muted">${offsetStr}</span>   ${hexSpans}   ${asciiSpans}\n`;
  }

  hexBox.innerHTML = html;
}

window.handleByteHover = function(span) {
  const offset = parseInt(span.dataset.offset, 10);
  const b = parseInt(span.dataset.byte, 10);
  const hexVal = b.toString(16).padStart(2, "0").toUpperCase();
  const binVal = b.toString(2).padStart(8, "0");
  const asciiChar = (b >= 32 && b <= 126) ? `'${String.fromCharCode(b)}'` : "Non-printable";
  const layer = span.dataset.layer || "Payload";

  const hoverBox = $("#sniffByteHoverInfo");
  if (hoverBox) {
    hoverBox.innerHTML = `
      <span>Offset: <b>0x${offset.toString(16).padStart(4, "0")} (${offset})</b></span>
      <span style="margin-left:12px">Hex: <b style="color:var(--accent)">0x${hexVal}</b></span>
      <span style="margin-left:12px">Dec: <b>${b}</b></span>
      <span style="margin-left:12px">Bin: <b style="color:#34d399">${binVal}</b></span>
      <span style="margin-left:12px">ASCII: <b>${esc(asciiChar)}</b></span>
      <span style="margin-left:auto;color:var(--accent2);font-weight:700">Layer: ${esc(layer)}</span>
    `;
  }
};

/* ========================================================================= */
/* DEEP PACKET INTELLIGENCE DRAWER MODAL                                     */
/* ========================================================================= */
function openPacketDrawerModal() {
  const modal = $("#packetDrawerModal");
  if (!modal) return;
  modal.hidden = false;
  modal.classList.add("active");

  const pkt = currentPackets.find(p => p.id === selectedPacketId) || currentPackets[0];
  if (pkt) {
    updatePacketDrawerContent(pkt);
  }
}

function closePacketDrawerModal() {
  const modal = $("#packetDrawerModal");
  if (modal) {
    modal.classList.remove("active");
    modal.hidden = true;
  }
}

function updatePacketDrawerContent(pkt) {
  const d = pkt.dissection || {};
  const ip = d.ipv4 || {};
  const trans = d.transport || {};
  const app = d.application || {};
  const exp = d.expert_info || {};

  if ($("#drawerPktSummary")) {
    $("#drawerPktSummary").textContent = `Packet #${pkt.id} · ${pkt.protocol} · ${pkt.src}:${pkt.sport || ""} ➔ ${pkt.dst}:${pkt.dport || ""} (${pkt.len} Bytes)`;
  }
  if ($("#drawerExpertBadge")) {
    $("#drawerExpertBadge").textContent = exp.severity || "INFO";
    $("#drawerExpertBadge").className = `badge ${exp.severity === "WARN" ? "badge-risk-high" : exp.severity === "NOTE" ? "badge-risk-medium" : "badge-risk-safe"}`;
  }
  if ($("#drawerProtoNameBadge")) {
    $("#drawerProtoNameBadge").textContent = pkt.protocol;
  }

  // 1. AI & RFC Protocol Explainer
  const explainerBox = $("#drawerExpertExplainer");
  if (explainerBox) {
    let explanation = "";
    if (pkt.protocol.includes("TLS") || pkt.protocol.includes("HTTPS")) {
      explanation = `<b>Transport Layer Security (TLS/HTTPS):</b> Encrypted socket communication safeguarding web traffic from eavesdropping. ` +
        (app.details?.sni ? `The client requested host <b>${esc(app.details.sni)}</b> via Server Name Indication.` : `Encrypted application data flow.`);
    } else if (pkt.protocol === "DNS") {
      explanation = `<b>Domain Name System (DNS / RFC 1035):</b> Resolves human-readable hostnames to IP addresses. ` +
        (app.details?.dns_query ? `Querying domain <b>${esc(app.details.dns_query)}</b> for <b>${esc(app.details.dns_type || "A")}</b> record.` : `UDP port 53 query.`);
    } else if (pkt.protocol === "HTTP") {
      explanation = `<b>Hypertext Transfer Protocol (HTTP / RFC 2616):</b> Unencrypted web transfer. Headers and payloads are transmitted in cleartext. ` +
        (app.details?.http?.request_line ? `<br><b>Request:</b> <code>${esc(app.details.http.request_line)}</code>` : "");
    } else if (pkt.protocol === "QUIC") {
      explanation = `<b>QUIC Protocol (RFC 9000):</b> Next-generation multiplexed transport over UDP with built-in TLS 1.3 encryption and 0-RTT handshakes.`;
    } else if (pkt.protocol === "ICMP") {
      explanation = `<b>Internet Control Message Protocol (ICMP / RFC 792):</b> Network diagnostic and routing feedback messages (e.g. Ping Echo Request/Reply).`;
    } else {
      explanation = `<b>${esc(pkt.protocol)} Stream:</b> Transporting ${pkt.len} bytes of network payload between endpoints.`;
    }

    explainerBox.innerHTML = explanation;
  }

  // 2. Detailed Bitwise Header Fields
  const fieldsBox = $("#drawerDetailedFields");
  if (fieldsBox) {
    fieldsBox.innerHTML = `
      <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">Frame Number:</span><span class="s1-th">#${pkt.id}</span></div>
      <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">Capture Timestamp:</span><span class="s1-th">${pkt.time_str}</span></div>
      <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">IPv4 Total Length:</span><span class="s1-th">${ip.total_len || pkt.len} Bytes</span></div>
      <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">IP Identification:</span><span class="s1-th">${ip.ident || "0x0000"}</span></div>
      <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">Time to Live (TTL):</span><span class="s1-th">${ip.ttl || pkt.ttl} (${ip.os_guess || "OS"})</span></div>
      <div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">Transport Protocol:</span><span class="s1-th">${trans.type || pkt.ip_proto} (Port ${trans.sport || "—"} ➔ ${trans.dport || "—"})</span></div>
      ${trans.seq ? `<div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">TCP Sequence Number:</span><span class="s1-th">${trans.seq}</span></div>` : ""}
      ${trans.ack ? `<div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">TCP Acknowledgment:</span><span class="s1-th">${trans.ack}</span></div>` : ""}
      ${trans.window ? `<div class="s1-item"><span class="s1-sev"></span><span class="s1-msg">TCP Window Size:</span><span class="s1-th">${trans.window}</span></div>` : ""}
    `;
  }

  // 3. Decoded Strings from Payload
  const stringsBox = $("#drawerPayloadStrings");
  if (stringsBox) {
    const rawHex = pkt.raw_hex || "";
    let asciiStr = "";
    for (let i = 0; i < rawHex.length; i += 2) {
      const b = parseInt(rawHex.substr(i, 2), 16);
      if (b >= 32 && b <= 126) asciiStr += String.fromCharCode(b);
      else if (b === 10 || b === 13) asciiStr += "\n";
      else asciiStr += ".";
    }
    stringsBox.textContent = asciiStr || "(No printable payload characters)";
  }

  // 4. Endpoint GeoIP & Host Intelligence
  const geoBox = $("#drawerGeoIntelligence");
  if (geoBox) {
    const isLocalSrc = pkt.src.startsWith("192.168.") || pkt.src.startsWith("10.") || pkt.src.startsWith("172.") || pkt.src === "127.0.0.1";
    const isLocalDst = pkt.dst.startsWith("192.168.") || pkt.dst.startsWith("10.") || pkt.dst.startsWith("172.") || pkt.dst === "127.0.0.1";
    geoBox.innerHTML = `
      <div style="margin-bottom:8px">
        <span class="muted">Source:</span> <b>${esc(pkt.src)}</b>
        <span class="badge ${isLocalSrc ? "b-est" : "b-dev"}" style="margin-left:6px">${isLocalSrc ? "LAN / Local Host" : "WAN Public"}</span>
      </div>
      <div>
        <span class="muted">Destination:</span> <b>${esc(pkt.dst)}</b>
        <span class="badge ${isLocalDst ? "b-est" : "b-dev"}" style="margin-left:6px">${isLocalDst ? "LAN / Local Host" : "WAN Public"}</span>
      </div>
    `;
  }

  // 5. TCP Flags Matrix
  const flagsMatrix = $("#drawerTcpFlagsMatrix");
  if (flagsMatrix) {
    if (trans.type === "TCP") {
      const allFlags = ["SYN", "ACK", "FIN", "RST", "PSH", "URG", "ECE", "CWR"];
      flagsMatrix.innerHTML = allFlags.map(flg => `
        <span class="tcp-flag-badge ${trans.flags?.includes(flg) ? "on" : "off"}" style="padding:4px 10px;font-size:12px">
          ${trans.flags?.includes(flg) ? "✓ " : ""}${flg}
        </span>
      `).join("");
    } else {
      flagsMatrix.innerHTML = '<span class="muted" style="font-size:12px">N/A (Non-TCP Packet)</span>';
    }
  }

  // 6. Security & Anomaly Assessment
  const secBox = $("#drawerSecAssessment"), secBadge = $("#drawerSecRatingBadge");
  if (secBox) {
    secBox.innerHTML = `
      <div><b>Analysis:</b> ${esc(exp.summary || "Normal packet transmission")}</div>
      <div style="margin-top:6px;color:var(--muted)"><b>Guidance:</b> ${esc(exp.recommendation || "Traffic matches standard protocol behavior.")}</div>
    `;
  }
  if (secBadge) {
    secBadge.textContent = exp.severity === "WARN" ? "ATTENTION" : (exp.severity === "NOTE" ? "AUDIT" : "SAFE");
    secBadge.className = `badge ${exp.severity === "WARN" ? "badge-risk-high" : exp.severity === "NOTE" ? "badge-risk-medium" : "badge-risk-safe"}`;
  }
}

// Button Listeners for Pro Inspector
$("#openPacketDrawerBtn")?.addEventListener("click", openPacketDrawerModal);
$("#closePacketDrawerBtn")?.addEventListener("click", closePacketDrawerModal);
$("#closeInspectorBtn")?.addEventListener("click", () => {
  const insp = $("#sniffInspector");
  if (insp) insp.hidden = true;
  selectedPacketId = null;
  $$("#sniffTableBody tr").forEach(tr => tr.classList.remove("selected"));
});

$("#inspPrevPktBtn")?.addEventListener("click", () => {
  if (!currentPackets.length) return;
  const idx = currentPackets.findIndex(p => p.id === selectedPacketId);
  if (idx > 0) {
    selectPacketRow(currentPackets[idx - 1].id);
  }
});

$("#inspNextPktBtn")?.addEventListener("click", () => {
  if (!currentPackets.length) return;
  const idx = currentPackets.findIndex(p => p.id === selectedPacketId);
  if (idx >= 0 && idx < currentPackets.length - 1) {
    selectPacketRow(currentPackets[idx + 1].id);
  }
});

$("#inspFollowStreamBtn")?.addEventListener("click", () => {
  const pkt = currentPackets.find(p => p.id === selectedPacketId);
  if (pkt && pkt.sport && pkt.dport) {
    followStream(pkt.src, pkt.sport, pkt.dst, pkt.dport);
  } else {
    alert("This packet does not have active TCP/UDP ports for stream reconstruction.");
  }
});

$("#drawerFollowStreamBtn")?.addEventListener("click", () => {
  const pkt = currentPackets.find(p => p.id === selectedPacketId);
  if (pkt && pkt.sport && pkt.dport) {
    closePacketDrawerModal();
    followStream(pkt.src, pkt.sport, pkt.dst, pkt.dport);
  }
});

$("#copyHexDumpBtn")?.addEventListener("click", () => {
  const pkt = currentPackets.find(p => p.id === selectedPacketId);
  if (pkt && pkt.hex_dump) {
    navigator.clipboard.writeText(pkt.hex_dump);
    alert("Hex dump copied to clipboard!");
  }
});

$("#copyAsciiDumpBtn")?.addEventListener("click", () => {
  const pkt = currentPackets.find(p => p.id === selectedPacketId);
  if (pkt && pkt.raw_hex) {
    let ascii = "";
    for (let i = 0; i < pkt.raw_hex.length; i += 2) {
      const b = parseInt(pkt.raw_hex.substr(i, 2), 16);
      ascii += (b >= 32 && b <= 126) ? String.fromCharCode(b) : ".";
    }
    navigator.clipboard.writeText(ascii);
    alert("ASCII payload copied to clipboard!");
  }
});

$("#copyPayloadStringsBtn")?.addEventListener("click", () => {
  const text = $("#drawerPayloadStrings")?.textContent || "";
  navigator.clipboard.writeText(text);
  alert("Payload strings copied to clipboard!");
});

window.followStream = async function(src, sport, dst, dport) {
  const modal = $("#streamModal"), ep = $("#streamEndpoints"), box = $("#streamContentBox"), badge = $("#streamTurnsBadge");
  if (!modal || !box) return;
  modal.hidden = false;
  modal.classList.add("active");
  ep.textContent = `${src}:${sport}  ⇄  ${dst}:${dport}`;
  box.innerHTML = '<span class="muted">Reassembling conversation stream…</span>';
  try {
    const d = await api(`/api/sniffer/follow-stream?src=${encodeURIComponent(src)}&sport=${sport}&dst=${encodeURIComponent(dst)}&dport=${dport}`);
    if (badge) badge.textContent = `${d.turns_count || 0} Turns (${fmtBytes(d.total_bytes)})`;
    const turns = d.turns || [];
    if (!turns.length) {
      box.innerHTML = '<span class="muted">No conversation payload segments found in current packet buffer.</span>';
      return;
    }
    box.innerHTML = turns.map(t => `
      <div class="stream-turn ${t.origin}">
        <div class="stream-turn-head">
          <span>${t.origin === 'client' ? '🔴 CLIENT (' + esc(t.from) + ' ➔ ' + esc(t.to) + ')' : '🔵 SERVER (' + esc(t.from) + ' ➔ ' + esc(t.to) + ')'}</span>
          <span>${t.bytes} bytes · ${esc(t.protocol)}</span>
        </div>
        <div class="stream-payload">${esc(t.text)}</div>
      </div>
    `).join("");
  } catch (e) {
    box.innerHTML = `<span class="err">Stream error: ${esc(e.message)}</span>`;
  }
};
$("#closeStreamBtn")?.addEventListener("click", () => {
  const modal = $("#streamModal");
  if (modal) { modal.hidden = true; modal.classList.remove("active"); }
});

window.openConvsModal = async function() {
  const modal = $("#convsModal"), tbody = $("#convsTableBody");
  if (!modal || !tbody) return;
  modal.hidden = false;
  modal.classList.add("active");
  tbody.innerHTML = '<tr><td colspan="7" class="muted" style="text-align:center;padding:20px">Loading conversations matrix…</td></tr>';
  try {
    const d = await api("/api/sniffer/conversations?limit=50");
    const list = d.conversations || [];
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="muted" style="text-align:center;padding:20px">No active conversations captured yet. Start capture to record traffic.</td></tr>';
      return;
    }
    let nodesMap = new Map();
    let edgesData = [];
    
    tbody.innerHTML = list.map(c => {
      const p1 = c.endpoint_a.split(":"), p2 = c.endpoint_b.split(":");
      const srcIp = p1[0], srcPort = p1[1] || 0, dstIp = p2[0], dstPort = p2[1] || 0;
      
      if (!nodesMap.has(srcIp)) nodesMap.set(srcIp, { id: srcIp, label: srcIp, shape: 'dot', size: 10, color: '#38bdf8' });
      if (!nodesMap.has(dstIp)) nodesMap.set(dstIp, { id: dstIp, label: dstIp, shape: 'dot', size: 10, color: '#2dd4bf' });
      edgesData.push({ from: srcIp, to: dstIp, value: c.total_bytes, title: `${fmtBytes(c.total_bytes)}`, color: { opacity: 0.5 } });

      return `
        <tr>
          <td class="mono"><b>${esc(c.endpoint_a)}</b></td>
          <td class="mono"><b>${esc(c.endpoint_b)}</b></td>
          <td><span class="badge b-tcp">${esc(c.proto)}</span></td>
          <td class="mono">${c.packets_a_to_b} ➔ / ${c.packets_b_to_a} ⬅</td>
          <td class="mono">${fmtBytes(c.bytes_a_to_b)} / ${fmtBytes(c.bytes_b_to_a)}</td>
          <td class="mono" style="color:var(--accent);font-weight:700">${fmtBytes(c.total_bytes)}</td>
          <td>
            <button class="btn" style="padding:2px 8px;font-size:11px" onclick="followStream('${srcIp}',${srcPort},'${dstIp}',${dstPort})">🌊 Follow</button>
          </td>
        </tr>
      `;
    }).join("");

    // Render Node Graph
    if (window.vis && document.getElementById("convsNodeGraph")) {
      document.getElementById("convsNodeGraph").innerHTML = "";
      new vis.Network(document.getElementById("convsNodeGraph"), {
        nodes: new vis.DataSet(Array.from(nodesMap.values())),
        edges: new vis.DataSet(edgesData)
      }, {
        nodes: { font: { color: "#e6edf7" } },
        edges: { color: { inherit: "from" }, smooth: { type: "continuous" } },
        physics: { stabilization: false, barnesHut: { gravitationalConstant: -3000 } }
      });
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" class="err">Error: ${esc(e.message)}</td></tr>`;
  }
};
$("#viewConvsBtn")?.addEventListener("click", openConvsModal);
$("#closeConvsBtn")?.addEventListener("click", () => {
  const modal = $("#convsModal");
  if (modal) { modal.hidden = true; modal.classList.remove("active"); }
});

// BPF Quick Filters
$$(".bpf-chip").forEach(btn => btn.addEventListener("click", () => {
  $$(".bpf-chip").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  const filter = btn.dataset.filter;
  if (filter === "SYN") {
    $("#sniffSearchInput").value = "SYN";
    $("#sniffProtoFilter").value = "ALL";
  } else if (filter === "DNS" || filter === "TLS/HTTPS" || filter === "HTTP" || filter === "UDP" || filter === "ICMP") {
    $("#sniffProtoFilter").value = filter;
    $("#sniffSearchInput").value = "";
  } else {
    $("#sniffSearchInput").value = "";
    $("#sniffProtoFilter").value = "ALL";
  }
  fetchSnifferData();
}));

async function startSnifferUI() {
  snifferActive = true;
  await api("/api/sniffer/start");
  $("#sniffStartBtn")?.classList.add("btn-accent");
  
  const dot = $("#sniffPulseDot");
  if (dot) {
    dot.style.opacity = "1";
    dot.style.animation = "pulseRed 1.5s infinite";
  }

  if (!snifferTimer) {
    snifferTimer = setInterval(fetchSnifferData, 1000);
  }
  fetchSnifferData();
}

async function stopSnifferUI() {
  snifferActive = false;
  await api("/api/sniffer/stop");
  
  const dot = $("#sniffPulseDot");
  if (dot) {
    dot.style.opacity = "0.3";
    dot.style.animation = "none";
  }
  
  if (snifferTimer) { clearInterval(snifferTimer); snifferTimer = null; }
  fetchSnifferData();
}

async function clearSnifferUI() {
  await api("/api/sniffer/clear");
  selectedPacketId = null;
  const insp = $("#sniffInspector");
  if (insp) insp.hidden = true;
  fetchSnifferData();
}

$("#sniffStartBtn")?.addEventListener("click", startSnifferUI);
$("#sniffStopBtn")?.addEventListener("click", stopSnifferUI);
$("#sniffClearBtn")?.addEventListener("click", clearSnifferUI);
$("#sniffProtoFilter")?.addEventListener("change", fetchSnifferData);
$("#sniffSearchInput")?.addEventListener("input", () => {
  clearTimeout(fetchSnifferData._t);
  fetchSnifferData._t = setTimeout(fetchSnifferData, 300);
});

/* ---------- hosts file & anti-telemetry manager ---------- */
async function loadHostsStatus() {
  const badge = $("#hostsShieldBadge"), ta = $("#hostsTextarea"), btn = $("#toggleAntiTelemetryBtn");
  if (!badge) return;
  try {
    const d = await api("/api/hosts/get");
    const active = d.blocklist_active;
    badge.textContent = active ? `🛡️ ACTIVE (${d.blocked_count} Domains Blocked)` : "OFF (Clear)";
    badge.className = `badge ${active ? "b-est" : "b-dev"}`;
    if (btn) {
      btn.textContent = active ? "🔓 Disable Anti-Telemetry Shield" : "🛡️ Enable Anti-Telemetry Shield";
      btn.className = `btn ${active ? "" : "btn-accent"}`;
    }
    if (ta) ta.value = d.content || "";
  } catch (e) {
    console.error("Hosts status error:", e);
  }
}

$("#toggleAntiTelemetryBtn")?.addEventListener("click", async () => {
  const badge = $("#hostsShieldBadge");
  const isCurrentlyActive = badge?.textContent.includes("ACTIVE");
  const action = isCurrentlyActive ? "Disable" : "Enable";
  if (!confirm(`Are you sure you want to ${action} the Anti-Telemetry & AdBlock Shield in your Windows hosts file?`)) return;
  try {
    const r = await api(`/api/hosts/toggle-blocklist?enable=${isCurrentlyActive ? "0" : "1"}`);
    if (r.ok) {
      alert(`Anti-Telemetry Shield ${isCurrentlyActive ? "disabled" : "enabled"} successfully!`);
      loadHostsStatus();
    } else {
      alert(`Error: ${r.error || "Permission Denied. Please run NetVisual as Administrator."}`);
    }
  } catch (e) {
    alert("Request error: " + e.message);
  }
});

$("#viewHostsBtn")?.addEventListener("click", () => {
  const box = $("#hostsEditorBox");
  if (box) box.hidden = !box.hidden;
});
$("#cancelHostsBtn")?.addEventListener("click", () => {
  const box = $("#hostsEditorBox");
  if (box) box.hidden = true;
});

/* ========================================================================= */
/* 1. TOPBAR LIVE BANDWIDTH SPARKLINE                                        */
/* ========================================================================= */
const sparklineHistory = [];
function renderTopbarSparkline(rxBps, txBps) {
  const canvas = $("#topbarSparkline");
  const label = $("#topbarSparklineVal");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  sparklineHistory.push({ rx: rxBps || 0, tx: txBps || 0 });
  if (sparklineHistory.length > 25) sparklineHistory.shift();

  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const maxVal = Math.max(...sparklineHistory.map(p => Math.max(p.rx, p.tx)), 1000);
  const step = w / (sparklineHistory.length - 1 || 1);

  // Draw RX (Download) in Cyan Area
  ctx.beginPath();
  ctx.moveTo(0, h);
  sparklineHistory.forEach((p, i) => {
    const y = h - (p.rx / maxVal) * (h - 4);
    ctx.lineTo(i * step, y);
  });
  ctx.lineTo((sparklineHistory.length - 1) * step, h);
  ctx.closePath();
  ctx.fillStyle = "rgba(56,189,248,0.25)";
  ctx.fill();

  ctx.beginPath();
  sparklineHistory.forEach((p, i) => {
    const y = h - (p.rx / maxVal) * (h - 4);
    if (i === 0) ctx.moveTo(0, y);
    else ctx.lineTo(i * step, y);
  });
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Draw TX (Upload) in Green Line
  ctx.beginPath();
  sparklineHistory.forEach((p, i) => {
    const y = h - (p.tx / maxVal) * (h - 4);
    if (i === 0) ctx.moveTo(0, y);
    else ctx.lineTo(i * step, y);
  });
  ctx.strokeStyle = "#34d399";
  ctx.lineWidth = 1.2;
  ctx.stroke();

  if (label) {
    const totalMbps = ((rxBps + txBps) * 8 / 1e6).toFixed(1);
    label.textContent = `${totalMbps} Mbps`;
  }
}

/* ========================================================================= */
/* 2. INTERACTIVE PHYSICS TOPOLOGY CANVAS & GLOWING FLOW PARTICLES           */
/* ========================================================================= */
let physicsNodes = [];
let physicsLinks = [];
let physicsParticles = [];
let physicsCanvasAnimId = null;
let physicsDragNode = null;
let physicsZoom = 1.0;
let physicsPan = { x: 0, y: 0 };
let physicsViewMode = "physics"; // "physics" | "svg"

function initPhysicsTopology(topoData) {
  const canvas = $("#topoCanvas");
  if (!canvas || !topoData) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const W = canvas.width = canvas.parentElement.clientWidth || 900;
  const H = canvas.height = 460;
  const cx = W / 2, cy = H / 2;

  // Build node graph
  const nodes = [];
  const links = [];
  const selfIp = topoData.self_ip;
  const gwIp = topoData.gateway;
  const neighbors = topoData.neighbors || [];

  // 1. This PC node
  const pcNode = {
    id: "this-pc",
    label: "This PC",
    ip: selfIp,
    kind: "this-pc",
    x: cx - 180,
    y: cy,
    vx: 0,
    vy: 0,
    radius: 22,
    color: "#38bdf8"
  };
  nodes.push(pcNode);

  // 2. Gateway node
  let gwNode = null;
  if (gwIp) {
    gwNode = {
      id: "gw",
      label: "Gateway",
      ip: gwIp,
      kind: "gateway",
      x: cx,
      y: cy,
      vx: 0,
      vy: 0,
      radius: 20,
      color: "#34d399"
    };
    nodes.push(gwNode);
    links.push({ source: pcNode, target: gwNode, dist: 180 });
  }

  // 3. Neighbor nodes
  const angleStep = (2 * Math.PI) / (neighbors.length || 1);
  neighbors.forEach((n, idx) => {
    const angle = idx * angleStep;
    const devNode = {
      id: n.ip,
      label: n.name || n.vendor || n.ip,
      ip: n.ip,
      mac: n.mac,
      vendor: n.vendor,
      kind: "device",
      x: cx + Math.cos(angle) * 160 + (Math.random() * 40 - 20),
      y: cy + Math.sin(angle) * 160 + (Math.random() * 40 - 20),
      vx: 0,
      vy: 0,
      radius: 14,
      color: n.is_new ? "#ef4444" : "#818cf8"
    };
    nodes.push(devNode);
    if (gwNode) links.push({ source: gwNode, target: devNode, dist: 140 });
    else links.push({ source: pcNode, target: devNode, dist: 160 });
  });

  physicsNodes = nodes;
  physicsLinks = links;

  // Initialize glowing flow particles
  physicsParticles = [];
  for (let i = 0; i < 20; i++) {
    if (links.length > 0) {
      const link = links[Math.floor(Math.random() * links.length)];
      physicsParticles.push({
        link,
        progress: Math.random(),
        speed: 0.005 + Math.random() * 0.01,
        color: Math.random() > 0.4 ? "#38bdf8" : "#34d399",
        size: 2.5 + Math.random() * 2
      });
    }
  }

  // Setup Mouse Interaction (Drag & Drop, Zoom, Pan)
  setupCanvasEvents(canvas);

  // Start Animation Loop
  if (physicsCanvasAnimId) cancelAnimationFrame(physicsCanvasAnimId);
  function step() {
    updatePhysics(W, H);
    drawPhysics(ctx, W, H);
    if (physicsViewMode === "physics") {
      physicsCanvasAnimId = requestAnimationFrame(step);
    }
  }
  step();
}

function setupCanvasEvents(canvas) {
  let isDragging = false;
  let isPanning = false;
  let startX = 0, startY = 0;

  canvas.onmousedown = (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - physicsPan.x) / physicsZoom;
    const my = (e.clientY - rect.top - physicsPan.y) / physicsZoom;

    // Find clicked node
    for (const node of physicsNodes) {
      const dx = node.x - mx, dy = node.y - my;
      if (Math.hypot(dx, dy) < node.radius + 6) {
        physicsDragNode = node;
        isDragging = true;
        return;
      }
    }
    isPanning = true;
    startX = e.clientX - physicsPan.x;
    startY = e.clientY - physicsPan.y;
  };

  window.onmousemove = (e) => {
    if (isDragging && physicsDragNode) {
      const rect = canvas.getBoundingClientRect();
      physicsDragNode.x = (e.clientX - rect.left - physicsPan.x) / physicsZoom;
      physicsDragNode.y = (e.clientY - rect.top - physicsPan.y) / physicsZoom;
      physicsDragNode.vx = physicsDragNode.vy = 0;
    } else if (isPanning) {
      physicsPan.x = e.clientX - startX;
      physicsPan.y = e.clientY - startY;
    }
  };

  window.onmouseup = () => {
    isDragging = false;
    isPanning = false;
    physicsDragNode = null;
  };

  canvas.onwheel = (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    physicsZoom = Math.max(0.4, Math.min(2.5, physicsZoom * zoomFactor));
  };
}

function updatePhysics(W, H) {
  // Spring forces on links
  physicsLinks.forEach(link => {
    const dx = link.target.x - link.source.x;
    const dy = link.target.y - link.source.y;
    const dist = Math.hypot(dx, dy) || 1;
    const force = (dist - link.dist) * 0.015;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;

    if (link.source !== physicsDragNode) {
      link.source.vx += fx;
      link.source.vy += fy;
    }
    if (link.target !== physicsDragNode) {
      link.target.vx -= fx;
      link.target.vy -= fy;
    }
  });

  // Repulsion forces between nodes
  for (let i = 0; i < physicsNodes.length; i++) {
    for (let j = i + 1; j < physicsNodes.length; j++) {
      const a = physicsNodes[i], b = physicsNodes[j];
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 1;
      if (dist < 220) {
        const rep = 800 / (dist * dist);
        const rx = (dx / dist) * rep;
        const ry = (dy / dist) * rep;
        if (a !== physicsDragNode) { a.vx -= rx; a.vy -= ry; }
        if (b !== physicsDragNode) { b.vx += rx; b.vy += ry; }
      }
    }
  }

  // Update positions with damping
  physicsNodes.forEach(node => {
    if (node === physicsDragNode) return;
    node.vx *= 0.88;
    node.vy *= 0.88;
    node.x += node.vx;
    node.y += node.vy;

    // Soft bounds
    node.x = Math.max(40, Math.min(W - 40, node.x));
    node.y = Math.max(40, Math.min(H - 40, node.y));
  });

  // Update flow particles
  physicsParticles.forEach(p => {
    p.progress += p.speed;
    if (p.progress >= 1) {
      p.progress = 0;
      if (physicsLinks.length > 0) {
        p.link = physicsLinks[Math.floor(Math.random() * physicsLinks.length)];
      }
    }
  });
}

function drawPhysics(ctx, W, H) {
  ctx.save();
  ctx.clearRect(0, 0, W, H);
  ctx.translate(physicsPan.x, physicsPan.y);
  ctx.scale(physicsZoom, physicsZoom);

  // Draw links
  physicsLinks.forEach(link => {
    ctx.beginPath();
    ctx.moveTo(link.source.x, link.source.y);
    ctx.lineTo(link.target.x, link.target.y);
    ctx.strokeStyle = "rgba(148, 163, 184, 0.25)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });

  // Draw glowing flow particles
  physicsParticles.forEach(p => {
    if (!p.link) return;
    const x = p.link.source.x + (p.link.target.x - p.link.source.x) * p.progress;
    const y = p.link.source.y + (p.link.target.y - p.link.source.y) * p.progress;
    ctx.beginPath();
    ctx.arc(x, y, p.size, 0, 2 * Math.PI);
    ctx.fillStyle = p.color;
    ctx.shadowColor = p.color;
    ctx.shadowBlur = 8;
    ctx.fill();
    ctx.shadowBlur = 0;
  });

  // Draw nodes
  physicsNodes.forEach(node => {
    // Outer glow
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.radius + 6, 0, 2 * Math.PI);
    ctx.fillStyle = `${node.color}22`;
    ctx.fill();

    // Node body
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.radius, 0, 2 * Math.PI);
    ctx.fillStyle = `${node.color}33`;
    ctx.strokeStyle = node.color;
    ctx.lineWidth = 2.5;
    ctx.fill();
    ctx.stroke();

    // Icon / Symbol inside node
    ctx.fillStyle = node.color;
    ctx.font = "bold 11px system-ui";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const symbol = node.kind === "this-pc" ? "PC" : (node.kind === "gateway" ? "GW" : "•");
    ctx.fillText(symbol, node.x, node.y);

    // Label under node
    ctx.fillStyle = "#f1f5f9";
    ctx.font = "600 11px system-ui";
    ctx.fillText(node.label.length > 18 ? node.label.slice(0, 16) + "…" : node.label, node.x, node.y + node.radius + 14);

    // IP under label
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px monospace";
    ctx.fillText(node.ip, node.x, node.y + node.radius + 26);
  });

  ctx.restore();
}

$("#topoViewPhysicsBtn")?.addEventListener("click", () => {
  physicsViewMode = "physics";
  $("#topoCanvas").style.display = "block";
  $("#topoSvg").style.display = "none";
  $("#topoViewPhysicsBtn").classList.add("btn-accent");
  $("#topoViewSvgBtn").classList.remove("btn-accent");
  loadTopology();
});

$("#topoViewSvgBtn")?.addEventListener("click", () => {
  physicsViewMode = "svg";
  $("#topoCanvas").style.display = "none";
  $("#topoSvg").style.display = "block";
  $("#topoViewSvgBtn").classList.add("btn-accent");
  $("#topoViewPhysicsBtn").classList.remove("btn-accent");
  if (physicsCanvasAnimId) cancelAnimationFrame(physicsCanvasAnimId);
  loadTopology();
});

/* ========================================================================= */
/* 3. QUICK COMMAND PALETTE (Ctrl + K)                                       */
/* ========================================================================= */
const commandList = [
  { id: "tab-live", title: "📊 Live Network Monitor", category: "Navigation", icon: "📊", action: () => switchTab("live") },
  { id: "tab-trends", title: "📈 30-Day Trends & Insights", category: "Navigation", icon: "📈", action: () => switchTab("trends") },
  { id: "tab-topology", title: "🗺️ Network Topology Canvas", category: "Navigation", icon: "🗺️", action: () => switchTab("topology") },
  { id: "tab-geomap", title: "🌍 World Geo Map", category: "Navigation", icon: "🌍", action: () => switchTab("geomap") },
  { id: "tab-security", title: "🛡️ Cyber Security & DNS Leak", category: "Navigation", icon: "🛡️", action: () => switchTab("security") },
  { id: "tab-ai", title: "🤖 AI Assistant", category: "Navigation", icon: "🤖", action: () => switchTab("ai") },
  { id: "tab-sniffer", title: "🦈 Live Packet Sniffer", category: "Navigation", icon: "🦈", action: () => switchTab("sniffer") },
  { id: "tab-speedtest", title: "⚡ Speed Test & QoS", category: "Navigation", icon: "⚡", action: () => switchTab("speedtest") },
  { id: "tab-wifi", title: "📶 Wi-Fi Spectrum Analyzer", category: "Navigation", icon: "📶", action: () => switchTab("wifi") },
  { id: "tab-netprofiles", title: "📁 Network Profiles", category: "Navigation", icon: "📁", action: () => switchTab("netprofiles") },
  { id: "tab-nettools", title: "🧰 Network Tools & System Repair", category: "Navigation", icon: "🧰", action: () => switchTab("nettools") },
  { id: "tab-devices", title: "🖥️ Discovered Devices Inventory", category: "Navigation", icon: "🖥️", action: () => switchTab("devices") },
  { id: "tab-connections", title: "🔌 Active Sockets & Process Bandwidth", category: "Navigation", icon: "🔌", action: () => switchTab("connections") },
  { id: "act-speedtest", title: "⚡ Run Full Speed Test", category: "Action", icon: "⚡", action: () => { switchTab("speedtest"); $("#startSpeedtestBtn")?.click(); } },
  { id: "act-repair", title: "🛠️ 1-Click Network Repair & Flush DNS", category: "Action", icon: "🛠️", action: () => $("#quickRepairBtn")?.click() },
  { id: "act-shield", title: "🛡️ Toggle Windows Anti-Telemetry Shield", category: "Action", icon: "🛡️", action: () => $("#toggleAntiTelemetryBtn")?.click() },
  { id: "act-report", title: "📄 Generate Network Health Audit Report", category: "Action", icon: "📄", action: () => $("#healthReportBtn")?.click() },
  { id: "act-hud", title: "🪟 Launch Floating Desktop HUD", category: "Action", icon: "🪟", action: () => $("#hudModeBtn")?.click() },
  { id: "act-sniff-start", title: "▶️ Start Live Packet Capture", category: "Action", icon: "▶️", action: () => { switchTab("sniffer"); startSnifferUI(); } },
  { id: "act-sniff-stop", title: "⏹️ Stop Packet Capture", category: "Action", icon: "⏹️", action: () => stopSnifferUI() },
  { id: "act-prof-home", title: "🏠 Apply Home DHCP Profile", category: "Profile", icon: "🏠", action: () => api("/api/profiles/apply?id=p_home") },
  { id: "act-prof-work", title: "💼 Apply Work Static IP Profile", category: "Profile", icon: "💼", action: () => api("/api/profiles/apply?id=p_work") },
  { id: "act-prof-gaming", title: "🎮 Apply Low-Ping Gaming Profile", category: "Profile", icon: "🎮", action: () => api("/api/profiles/apply?id=p_gaming") },
  { id: "act-prof-shield", title: "🛡️ Apply Secure Shield Profile", category: "Profile", icon: "🛡️", action: () => api("/api/profiles/apply?id=p_secure") },
];

let cmdSelectedIndex = 0;
function openCommandPalette() {
  const modal = $("#cmdPaletteModal");
  const input = $("#cmdPaletteInput");
  if (!modal || !input) return;
  modal.hidden = false;
  input.value = "";
  cmdSelectedIndex = 0;
  renderCommandResults("");
  setTimeout(() => input.focus(), 50);
}

function closeCommandPalette() {
  const modal = $("#cmdPaletteModal");
  if (modal) modal.hidden = true;
}

function renderCommandResults(query) {
  const container = $("#cmdPaletteResults");
  if (!container) return;
  const q = (query || "").trim().toLowerCase();

  // Combine static commands with discovered devices
  let items = [...commandList];
  if (devList && devList.length) {
    devList.forEach(d => {
      items.push({
        id: `dev-${d.ip}`,
        title: `🖥️ Device: ${d.ip} (${d.vendor || d.label || "Host"})`,
        category: "Device",
        icon: "🖥️",
        action: () => { switchTab("devices"); highlightDevice(d.ip); }
      });
    });
  }

  const filtered = items.filter(it => !q || it.title.toLowerCase().includes(q) || it.category.toLowerCase().includes(q));

  if (!filtered.length) {
    container.innerHTML = '<div class="muted" style="padding:20px;text-align:center">No matching commands or devices found.</div>';
    return;
  }

  cmdSelectedIndex = Math.max(0, Math.min(filtered.length - 1, cmdSelectedIndex));

  container.innerHTML = filtered.map((it, idx) => `
    <div class="cmd-item ${idx === cmdSelectedIndex ? "selected" : ""}" data-idx="${idx}">
      <span class="cmd-item-icon">${it.icon}</span>
      <div class="cmd-item-info">
        <span class="cmd-item-title">${esc(it.title)}</span>
      </div>
      <span class="cmd-item-tag">${esc(it.category)}</span>
    </div>
  `).join("");

  $$(".cmd-item").forEach(el => {
    el.addEventListener("click", () => {
      const idx = parseInt(el.dataset.idx, 10);
      filtered[idx]?.action();
      closeCommandPalette();
    });
  });
}

$("#cmdPaletteBtn")?.addEventListener("click", openCommandPalette);
$("#cmdPaletteInput")?.addEventListener("input", (e) => {
  cmdSelectedIndex = 0;
  renderCommandResults(e.target.value);
});

window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    const modal = $("#cmdPaletteModal");
    if (modal && !modal.hidden) closeCommandPalette();
    else openCommandPalette();
  } else if (e.key === "Escape") {
    closeCommandPalette();
  } else if ($("#cmdPaletteModal") && !$("#cmdPaletteModal").hidden) {
    const items = $$(".cmd-item");
    if (!items.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      cmdSelectedIndex = (cmdSelectedIndex + 1) % items.length;
      renderCommandResults($("#cmdPaletteInput").value);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      cmdSelectedIndex = (cmdSelectedIndex - 1 + items.length) % items.length;
      renderCommandResults($("#cmdPaletteInput").value);
    } else if (e.key === "Enter") {
      e.preventDefault();
      items[cmdSelectedIndex]?.click();
    }
  }
});

/* ========================================================================= */
/* 4. PROCESS BANDWIDTH RANKING & 1-CLICK FIREWALL BLOCKER                   */
/* ========================================================================= */
async function loadProcessBandwidth() {
  const container = $("#procBwList");
  const totalRateLbl = $("#procBwTotalRate");
  if (!container) return;

  try {
    const d = await api("/api/processes/bandwidth");
    const procs = d.processes || [];
    if (totalRateLbl) {
      const totalRx = fmtBytes(d.total_rx_bps || 0) + "/s";
      const totalTx = fmtBytes(d.total_tx_bps || 0) + "/s";
      totalRateLbl.textContent = `Total: ↓ ${totalRx} · ↑ ${totalTx}`;
    }

    if (!procs.length) {
      container.innerHTML = '<div class="muted" style="padding:10px 0;font-size:12px">No active application sockets detected.</div>';
      return;
    }

    container.innerHTML = procs.map(p => `
      <div class="proc-bw-item">
        <div class="proc-bw-name" title="${esc(p.path || p.process)}">
          <span>📦</span> <b>${esc(p.process)}</b>
        </div>
        <div class="proc-bw-bar-wrap">
          <div class="proc-bw-bar">
            <div class="proc-bw-fill" style="width:${Math.max(3, p.pct)}%"></div>
          </div>
          <span class="proc-bw-pct">${p.pct}%</span>
        </div>
        <div class="proc-bw-rate">${fmtBytes(p.total_bps)}/s</div>
        <div class="proc-bw-sockets">${p.established} est / ${p.total_conns} total</div>
        <div>
          ${p.path ? `<button class="btn" style="padding:2px 8px;font-size:11px;color:var(--danger);border-color:rgba(239,68,68,0.3)" onclick="blockAppInFirewall('${esc(p.path.replace(/\\/g, '\\\\'))}')" title="Block outbound network access for this executable in Windows Defender Firewall">🛑 Block</button>` : `<span class="muted" style="font-size:11px">System</span>`}
        </div>
      </div>
    `).join("");
  } catch (e) {
    container.innerHTML = `<div class="err">Error loading process bandwidth: ${esc(e.message)}</div>`;
  }
}

async function blockAppInFirewall(path) {
  if (!confirm(`Block outbound network access for this application in Windows Defender Firewall?\n\n${path}`)) return;
  try {
    const res = await api(`/api/firewall/block`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path })
    });
    if (res.ok) {
      alert(`Firewall Rule Created:\n${res.output}`);
      loadProcessBandwidth();
    } else {
      alert(`Firewall Error: ${res.error || "Requires Administrator privileges."}`);
    }
  } catch (e) {
    alert("Request failed: " + e.message);
  }
}

/* ========================================================================= */
/* 5. MULTI-THREADED LAN PORT & VULNERABILITY SCANNER                        */
/* ========================================================================= */
let portScanTarget = "127.0.0.1";
let portScanPreset = "common";

function openPortScanModal(ip) {
  portScanTarget = ip || "127.0.0.1";
  const modal = $("#portScanModal");
  const targetLbl = $("#portScanTargetHost");
  if (modal) {
    modal.hidden = false;
    modal.classList.add("active");
  }
  if (targetLbl) targetLbl.textContent = `Target: ${portScanTarget}`;
  runPortScan();
}

async function runPortScan() {
  const tbody = $("#portScanTableBody");
  const badge = $("#portScanRiskBadge");
  const btn = $("#startPortScanBtn");
  if (!tbody) return;

  if (btn) btn.disabled = true;
  if (badge) { badge.textContent = "SCANNING…"; badge.className = "badge"; }
  tbody.innerHTML = '<tr><td colspan="6" class="muted" style="text-align:center;padding:25px">⚡ Probing open TCP ports & banner inspection in parallel…</td></tr>';

  let portsParam = "";
  if (portScanPreset === "web") portsParam = "&ports=80,443,8080,8443";
  else if (portScanPreset === "remote") portsParam = "&ports=22,23,3389,5900";
  else if (portScanPreset === "databases") portsParam = "&ports=1433,3306,5432,27017";

  try {
    const d = await api(`/api/scan/host?ip=${encodeURIComponent(portScanTarget)}${portsParam}`);
    const ports = d.ports || [];
    const openPorts = d.open_entries || [];

    if (badge) {
      badge.textContent = `${d.risk_summary} RISK (${openPorts.length} Open)`;
      badge.className = `badge ${d.risk_summary === "CRITICAL" ? "badge-risk-critical" : d.risk_summary === "HIGH" ? "badge-risk-high" : d.risk_summary === "MEDIUM" ? "badge-risk-medium" : "badge-risk-safe"}`;
    }

    if (!ports.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="muted" style="text-align:center;padding:20px">No ports responded. Host may be offline or firewalled.</td></tr>';
      return;
    }

    tbody.innerHTML = ports.map(p => `
      <tr style="${p.open ? "background:rgba(56,189,248,0.06)" : ""}">
        <td class="mono"><b>${p.port}</b></td>
        <td><b>${esc(p.service)}</b></td>
        <td><span class="badge ${p.risk === "CRITICAL" ? "badge-risk-critical" : p.risk === "HIGH" ? "badge-risk-high" : p.risk === "MEDIUM" ? "badge-risk-medium" : "badge-risk-safe"}">${esc(p.risk)}</span></td>
        <td>${p.open ? '<span class="badge b-yes">OPEN</span>' : '<span class="muted">Closed</span>'}</td>
        <td class="mono">${p.ms != null ? p.ms + " ms" : "—"}</td>
        <td>
          <div style="font-weight:600">${esc(p.desc)}</div>
          ${p.banner ? `<div class="mono" style="font-size:11px;color:var(--accent);margin-top:2px">Banner: ${esc(p.banner)}</div>` : ""}
        </td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="err">Scan error: ${esc(e.message)}</td></tr>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

$("#startPortScanBtn")?.addEventListener("click", runPortScan);
$("#closePortScanBtn")?.addEventListener("click", () => {
  const modal = $("#portScanModal");
  if (modal) { modal.hidden = true; modal.classList.remove("active"); }
});

$$(".port-preset-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    $$(".port-preset-chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    portScanPreset = chip.dataset.preset || "common";
    runPortScan();
  });
});

/* ========================================================================= */
/* 6. CSV / EXCEL EXPORT HANDLERS                                            */
/* ========================================================================= */
$("#connCsvBtn")?.addEventListener("click", () => {
  window.open("/api/export/connections", "_blank");
});

/* ========================================================================= */
/* 7. WORLD MAP PRO ENGINE & MULTI-LAYER CYBER RADAR                         */
/* ========================================================================= */
let geoMap = null;
let geoData = null;
let geoMarkersGroup = null;
let geoFlightLinesGroup = null;
let geoCountryBubblesGroup = null;
let geoLatencyRingsGroup = null;
let geoDayNightLayer = null;
let geoTileLayer = null;
let geoAnimFrame = null;
let geoFlowParticles = [];
let geoActiveTheme = "cyber";

const GEO_TILE_URLS = {
  cyber: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  standard: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  satellite: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  osm: "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"
};

async function loadGeoMap() {
  const container = $("#geomapCanvas");
  if (!container || typeof L === "undefined") return;

  if (!geoMap) {
    initGeoMapInstance();
  } else {
    setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 50);
    setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 250);
    setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 500);
  }

  try {
    const data = await api("/api/geomap");
    geoData = data;
    renderGeoData(data);
    setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 100);
    setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 350);
  } catch (e) {
    console.error("GeoMap fetch error:", e);
  }
}

function initGeoMapInstance() {
  geoMap = L.map("geomapCanvas", {
    center: [28, 15],
    zoom: 2,
    minZoom: 2,
    maxZoom: 18,
    zoomControl: true,
    attributionControl: false
  });

  setGeoMapTileTheme(geoActiveTheme);

  // Initialize Layer Groups
  geoLatencyRingsGroup = L.layerGroup().addTo(geoMap);
  geoFlightLinesGroup = L.layerGroup().addTo(geoMap);
  geoCountryBubblesGroup = L.layerGroup().addTo(geoMap);
  geoMarkersGroup = L.layerGroup().addTo(geoMap);

  // Setup Event Listeners for Controls
  setupGeoMapControls();

  // Start Animation Loop for Flow Beams
  startGeoFlowAnimation();

  // Force map container dimension recalculation
  setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 50);
  setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 200);
  setTimeout(() => { if (geoMap) geoMap.invalidateSize(true); }, 500);
}

function setGeoMapTileTheme(theme) {
  geoActiveTheme = theme;
  if (geoTileLayer && geoMap) {
    geoMap.removeLayer(geoTileLayer);
  }
  const url = GEO_TILE_URLS[theme] || GEO_TILE_URLS.cyber;
  const isOsmHot = url.includes("openstreetmap.fr");
  const className = (theme === "cyber") ? "geomap-cyber-tiles" : "";
  geoTileLayer = L.tileLayer(url, {
    maxZoom: 18,
    className: className,
    subdomains: isOsmHot ? ["a", "b", "c"] : []
  }).addTo(geoMap);
}

function setupGeoMapControls() {
  $("#geoStyleFilter")?.addEventListener("change", (e) => {
    setGeoMapTileTheme(e.target.value);
  });

  $("#geoResetViewBtn")?.addEventListener("click", () => {
    if (geoData?.origin) {
      geoMap.setView([geoData.origin.lat || 28, geoData.origin.lon || 15], 3);
    } else {
      geoMap.setView([28, 15], 2);
    }
  });

  $("#refreshGeoBtn")?.addEventListener("click", () => loadGeoMap());

  $("#geoSearch")?.addEventListener("input", () => filterAndRenderGeoData());
  $("#geoProcessFilter")?.addEventListener("change", () => filterAndRenderGeoData());
  $("#geoCloudFilter")?.addEventListener("change", () => filterAndRenderGeoData());

  // Layer Checkbox Toggles
  $("#layerFlowBeams")?.addEventListener("change", () => filterAndRenderGeoData());
  $("#layerCyberRisk")?.addEventListener("change", () => filterAndRenderGeoData());
  $("#layerCloudBadges")?.addEventListener("change", () => filterAndRenderGeoData());
  $("#layerCountryBubbles")?.addEventListener("change", () => filterAndRenderGeoData());
  $("#layerLatencyRings")?.addEventListener("change", () => filterAndRenderGeoData());
  $("#layerDayNight")?.addEventListener("change", () => toggleDayNightLayer());

  // Floating Layers Control Visibility
  $("#toggleLayersControlBtn")?.addEventListener("click", () => {
    const p = $("#geomapLayersControl");
    if (p) p.hidden = !p.hidden;
  });
  $("#closeLayersPanelBtn")?.addEventListener("click", () => {
    const p = $("#geomapLayersControl");
    if (p) p.hidden = true;
  });

  // Drawer Close Button
  $("#closeGeoDrawerBtn")?.addEventListener("click", closeGeoDrawer);
}

function renderGeoData(data) {
  if (!data) return;
  const origin = data.origin || { lat: 32.0853, lon: 34.7818, city: "Local PC", country: "Local" };
  const stats = data.stats || {};

  if ($("#geoDestCount")) $("#geoDestCount").textContent = stats.total_destinations || 0;
  if ($("#geoCountryCount")) $("#geoCountryCount").textContent = stats.countries_count || 0;
  if ($("#geoTopCountry")) $("#geoTopCountry").textContent = `Top: ${stats.top_country || "—"}`;
  if ($("#geoTopCloud")) $("#geoTopCloud").textContent = stats.top_cloud || "Direct";
  if ($("#geoTopCloudSub")) $("#geoTopCloudSub").textContent = `${stats.total_established || 0} active sockets`;
  
  const highRiskCount = stats.risk_distribution?.HIGH_RISK || 0;
  if ($("#geoRiskRating")) {
    $("#geoRiskRating").textContent = highRiskCount > 0 ? "ATTENTION" : "CLEAN";
    $("#geoRiskRating").style.color = highRiskCount > 0 ? "#f87171" : "#34d399";
  }
  if ($("#geoTopProcess")) {
    $("#geoTopProcess").textContent = `Top App: ${stats.top_process || "—"}`;
  }
  if ($("#geoOriginCity")) $("#geoOriginCity").textContent = origin.city || origin.country || "Local PC";
  if ($("#geoOriginIp")) $("#geoOriginIp").textContent = origin.ip ? `${origin.ip} (${origin.country || "Local"})` : "Local Host";

  // Populate Filter Dropdowns
  populateGeoFilters(data.destinations || []);

  // Render Map Layers & Table
  filterAndRenderGeoData();
}

function populateGeoFilters(destinations) {
  const procSel = $("#geoProcessFilter");
  if (procSel) {
    const currentVal = procSel.value;
    const procs = new Set();
    destinations.forEach(d => (d.processes || []).forEach(p => procs.add(p)));
    procSel.innerHTML = '<option value="ALL">All Processes</option>' + 
      Array.from(procs).sort().map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
    if (procs.has(currentVal)) procSel.value = currentVal;
  }
}

function filterAndRenderGeoData() {
  if (!geoData || !geoMap) return;
  const origin = geoData.origin || { lat: 32.0853, lon: 34.7818, city: "Local PC" };
  const rawDests = geoData.destinations || [];

  const searchQ = ($("#geoSearch")?.value || "").toLowerCase().trim();
  const procFilter = $("#geoProcessFilter")?.value || "ALL";
  const cloudFilter = $("#geoCloudFilter")?.value || "ALL";

  const showFlowBeams = $("#layerFlowBeams")?.checked ?? true;
  const showCyberRisk = $("#layerCyberRisk")?.checked ?? true;
  const showCloudBadges = $("#layerCloudBadges")?.checked ?? true;
  const showCountryBubbles = $("#layerCountryBubbles")?.checked ?? true;
  const showLatencyRings = $("#layerLatencyRings")?.checked ?? true;

  // Filter destinations
  const filtered = rawDests.filter(d => {
    if (procFilter !== "ALL" && !(d.processes || []).includes(procFilter)) return false;
    if (cloudFilter !== "ALL" && d.cloud_provider !== cloudFilter) return false;
    if (searchQ) {
      const hay = `${d.ip} ${d.city} ${d.country} ${d.isp} ${d.cloud_provider} ${d.category} ${(d.processes || []).join(" ")}`.toLowerCase();
      if (!hay.includes(searchQ)) return false;
    }
    return true;
  });

  // Clear existing map layers
  geoMarkersGroup.clearLayers();
  geoFlightLinesGroup.clearLayers();
  geoCountryBubblesGroup.clearLayers();
  geoLatencyRingsGroup.clearLayers();
  geoFlowParticles = [];

  // 1. Origin Marker
  const originIcon = L.divIcon({
    className: "custom-origin-pin",
    html: '<div class="geo-marker-origin" title="Your PC Location"></div>',
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });
  L.marker([origin.lat, origin.lon], { icon: originIcon })
    .bindPopup(`<b>📍 Your Machine (${esc(origin.city)})</b><br>${esc(origin.ip)}<br><small>${esc(origin.isp)}</small>`)
    .addTo(geoMarkersGroup);

  // 2. Latency Range Rings
  if (showLatencyRings && origin.lat && origin.lon) {
    renderLatencyIsochrones(origin);
  }

  // 3. Country Traffic Volume Bubbles
  if (showCountryBubbles) {
    renderCountryBubbles(filtered);
  }

  // 4. Destination Markers & Flight Arcs
  filtered.forEach(d => {
    if (!d.lat || !d.lon || (d.lat === 0 && d.lon === 0)) return;

    // Node Marker styling
    let markerHtml = "";
    let iconSize = [24, 24];
    let iconAnchor = [12, 12];

    if (showCloudBadges && d.cloud_provider) {
      const cClass = d.cloud_provider.toLowerCase().replace(/\s+/g, "");
      markerHtml = `<div class="cloud-badge-marker ${cClass}">${esc(d.cloud_provider)}</div>`;
      iconSize = [70, 20];
      iconAnchor = [35, 10];
    } else if (showCyberRisk) {
      let color = "#38bdf8";
      if (d.risk_level === "SAFE_CDN") color = "#34d399";
      else if (d.risk_level === "HIGH_RISK") color = "#f87171";
      else if (d.risk_level === "CLOUD") color = "#60a5fa";
      else if (d.risk_level === "RESIDENTIAL") color = "#c084fc";
      else color = "#facc15";

      markerHtml = `<div style="width:12px;height:12px;border-radius:50%;background:${color};border:2px solid #ffffff;box-shadow:0 0 8px ${color}"></div>`;
      iconSize = [14, 14];
      iconAnchor = [7, 7];
    } else {
      markerHtml = '<div style="width:10px;height:10px;border-radius:50%;background:#38bdf8;border:1.5px solid #ffffff;box-shadow:0 0 6px #38bdf8"></div>';
      iconSize = [12, 12];
      iconAnchor = [6, 6];
    }

    const mIcon = L.divIcon({
      className: "custom-dest-pin",
      html: markerHtml,
      iconSize: iconSize,
      iconAnchor: iconAnchor
    });

    const marker = L.marker([d.lat, d.lon], { icon: mIcon }).addTo(geoMarkersGroup);
    marker.on("click", () => openGeoDrawer(d));

    // Flight Curves & Animation Particles
    if (origin.lat && origin.lon) {
      const latlngs = createCurvedArcPoints([origin.lat, origin.lon], [d.lat, d.lon]);
      
      let lineColor = (d.risk_level === "HIGH_RISK") ? "#f87171" : (d.risk_level === "SAFE_CDN" ? "#34d399" : "#38bdf8");
      L.polyline(latlngs, {
        color: lineColor,
        weight: 1.5,
        opacity: 0.45,
        dashArray: "4, 6"
      }).addTo(geoFlightLinesGroup);

      if (showFlowBeams) {
        geoFlowParticles.push({
          points: latlngs,
          progress: Math.random(),
          speed: 0.006 + Math.min(d.established * 0.003, 0.02),
          color: lineColor
        });
      }
    }
  });

  // Render Table
  renderGeoTable(filtered);
}

function renderLatencyIsochrones(origin) {
  const rings = [
    { radiusKm: 1500, label: "< 30 ms (Regional)", color: "#34d399" },
    { radiusKm: 4000, label: "30-80 ms (Continental)", color: "#38bdf8" },
    { radiusKm: 8500, label: "80-160 ms (Trans-Atlantic)", color: "#facc15" },
    { radiusKm: 14000, label: "> 200 ms (Global / Asia)", color: "#c084fc" }
  ];

  rings.forEach(r => {
    L.circle([origin.lat, origin.lon], {
      radius: r.radiusKm * 1000,
      color: r.color,
      weight: 1,
      opacity: 0.25,
      fill: false,
      dashArray: "6, 10"
    }).bindTooltip(r.label, { permanent: false, direction: "top", className: "latency-tooltip" })
      .addTo(geoLatencyRingsGroup);
  });
}

function renderCountryBubbles(destinations) {
  const countryMap = {};
  destinations.forEach(d => {
    if (!d.country || d.country === "Unknown" || !d.lat) return;
    if (!countryMap[d.country]) {
      countryMap[d.country] = {
        country: d.country,
        country_code: d.country_code,
        lat: d.lat,
        lon: d.lon,
        sockets: 0,
        established: 0,
        processes: new Set()
      };
    }
    countryMap[d.country].sockets += d.total_sockets || 1;
    countryMap[d.country].established += d.established || 0;
    (d.processes || []).forEach(p => countryMap[d.country].processes.add(p));
  });

  Object.values(countryMap).forEach(c => {
    const radius = Math.min(60, 16 + Math.sqrt(c.sockets) * 8);
    const bubble = L.circleMarker([c.lat, c.lon], {
      radius: radius,
      color: "#38bdf8",
      weight: 1.5,
      opacity: 0.6,
      fillColor: "#0284c7",
      fillOpacity: 0.15
    }).addTo(geoCountryBubblesGroup);

    bubble.bindTooltip(`
      <div style="font-size:12px;line-height:1.4">
        <b>🌍 ${esc(c.country)}</b><br>
        <span style="color:#38bdf8;font-weight:700">${c.sockets} Sockets</span> (${c.established} Est.)<br>
        <small class="muted">Apps: ${Array.from(c.processes).slice(0, 3).join(", ") || "—"}</small>
      </div>
    `, { sticky: true });
  });
}

function toggleDayNightLayer() {
  const show = $("#layerDayNight")?.checked;
  if (!geoMap) return;

  if (!show) {
    if (geoDayNightLayer) {
      geoMap.removeLayer(geoDayNightLayer);
      geoDayNightLayer = null;
    }
    return;
  }

  // Compute Sun position for Day/Night shadow
  const now = new Date();
  const utcHours = now.getUTCHours() + now.getUTCMinutes() / 60;
  const sunLon = (12 - utcHours) * 15; // Sun longitude
  const dayOfYear = Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 1000 / 60 / 60 / 24);
  const declination = -23.44 * Math.cos((2 * Math.PI / 365) * (dayOfYear + 10)); // Solar declination approx

  // Build night polygon
  const nightCoords = [];
  nightCoords.push([-85, -180]);
  for (let lon = -180; lon <= 180; lon += 10) {
    const hourAngle = (lon - sunLon) * Math.PI / 180;
    const lat = -Math.atan(Math.cos(hourAngle) / Math.tan(declination * Math.PI / 180)) * 180 / Math.PI;
    nightCoords.push([Math.max(-85, Math.min(85, lat)), lon]);
  }
  nightCoords.push([-85, 180]);

  if (geoDayNightLayer) geoMap.removeLayer(geoDayNightLayer);
  geoDayNightLayer = L.polygon(nightCoords, {
    color: "transparent",
    fillColor: "#050b14",
    fillOpacity: 0.45
  }).addTo(geoMap);
}

function createCurvedArcPoints(start, end) {
  const lat1 = start[0], lon1 = start[1];
  const lat2 = end[0], lon2 = end[1];

  const midLat = (lat1 + lat2) / 2 + Math.sin(Math.abs(lon2 - lon1) * Math.PI / 360) * 15;
  const midLon = (lon1 + lon2) / 2;

  const points = [];
  const steps = 24;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    // Quadratic Bezier curve
    const lat = (1 - t) * (1 - t) * lat1 + 2 * (1 - t) * t * midLat + t * t * lat2;
    const lon = (1 - t) * (1 - t) * lon1 + 2 * (1 - t) * t * midLon + t * t * lon2;
    points.push([lat, lon]);
  }
  return points;
}

function startGeoFlowAnimation() {
  if (geoAnimFrame) cancelAnimationFrame(geoAnimFrame);

  function animate() {
    if (geoFlowParticles.length && geoMap && geoFlightLinesGroup) {
      geoFlowParticles.forEach(p => {
        p.progress += p.speed;
        if (p.progress >= 1) p.progress = 0;
      });
    }
    geoAnimFrame = requestAnimationFrame(animate);
  }
  geoAnimFrame = requestAnimationFrame(animate);
}

function renderGeoTable(destinations) {
  const tbody = $("#geoTableBody");
  const countBadge = $("#geoTableCount");
  if (countBadge) countBadge.textContent = `${destinations.length} endpoints`;
  if (!tbody) return;

  if (!destinations.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="muted" style="text-align:center;padding:24px">No matching external connections found.</td></tr>';
    return;
  }

  tbody.innerHTML = destinations.map(d => {
    const flag = d.country_code ? getFlagEmoji(d.country_code) : "🌐";
    let riskBadge = '<span class="badge badge-risk-safe">SAFE</span>';
    if (d.risk_level === "HIGH_RISK") riskBadge = '<span class="badge badge-risk-high">ATTENTION</span>';
    else if (d.risk_level === "CLOUD") riskBadge = '<span class="badge b-this">CLOUD</span>';
    else if (d.risk_level === "RESIDENTIAL") riskBadge = '<span class="badge b-dev">ISP</span>';

    return `
      <tr>
        <td class="mono"><b>${esc(d.ip)}</b></td>
        <td>${flag} <b>${esc(d.city)}</b>, ${esc(d.country)}</td>
        <td>
          ${d.cloud_provider ? `<span class="badge b-this" style="font-weight:700">${esc(d.cloud_provider)}</span> ` : ""}
          <span class="muted">${esc(d.isp || "—")}</span>
        </td>
        <td>${riskBadge} <small class="muted">${esc(d.category || "Host")}</small></td>
        <td class="proc">${(d.processes || []).map(p => `<span class="badge">${esc(p)}</span>`).join(" ") || "—"}</td>
        <td class="mono">${(d.ports || []).slice(0, 4).join(", ") || "—"}</td>
        <td class="mono" style="color:var(--accent);font-weight:700">${d.established} <small class="muted">(${d.total_sockets})</small></td>
        <td>
          <button class="btn" style="padding:3px 8px;font-size:11px" onclick="inspectGeoEndpoint('${esc(d.ip)}')">🔍 Inspect</button>
        </td>
      </tr>
    `;
  }).join("");
}

window.inspectGeoEndpoint = function(ip) {
  const d = (geoData?.destinations || []).find(x => x.ip === ip);
  if (d) {
    openGeoDrawer(d);
    if (geoMap && d.lat && d.lon) {
      geoMap.setView([d.lat, d.lon], 6, { animate: true });
    }
  }
};

function openGeoDrawer(d) {
  const drawer = $("#geoEndpointDrawer");
  if (!drawer) return;
  drawer.hidden = false;

  const flag = d.country_code ? getFlagEmoji(d.country_code) : "🌍";
  if ($("#drawerHostFlag")) $("#drawerHostFlag").textContent = flag;
  if ($("#drawerHostIp")) $("#drawerHostIp").textContent = d.ip;
  if ($("#drawerHostLocation")) $("#drawerHostLocation").textContent = `${d.city}, ${d.country}`;
  if ($("#drawerHostIsp")) $("#drawerHostIsp").textContent = d.isp || "Unknown ISP / Cloud";
  if ($("#drawerHostCategory")) $("#drawerHostCategory").textContent = d.category || "Public Host";
  if ($("#drawerHostCoords")) $("#drawerHostCoords").textContent = `${d.lat.toFixed(3)}, ${d.lon.toFixed(3)}`;
  if ($("#drawerHostCloudBadge")) {
    $("#drawerHostCloudBadge").textContent = d.cloud_provider || "Direct / Edge";
  }
  if ($("#drawerHostRiskBadge")) {
    $("#drawerHostRiskBadge").textContent = d.risk_level || "STANDARD";
    $("#drawerHostRiskBadge").className = `badge ${d.risk_level === "HIGH_RISK" ? "badge-risk-high" : d.risk_level === "SAFE_CDN" ? "badge-risk-safe" : "badge-risk-medium"}`;
  }
  if ($("#drawerHostPorts")) $("#drawerHostPorts").textContent = (d.ports || []).join(", ") || "None";
  if ($("#drawerHostSockets")) $("#drawerHostSockets").textContent = d.total_sockets || 0;
  if ($("#drawerHostEstablished")) $("#drawerHostEstablished").textContent = d.established || 0;

  const procBox = $("#drawerHostProcesses");
  if (procBox) {
    procBox.innerHTML = (d.processes || []).length 
      ? d.processes.map(p => `<span class="badge b-this" style="font-size:12px">📦 ${esc(p)}</span>`).join("")
      : '<span class="muted" style="font-size:12px">No active local processes attached</span>';
  }

  // Bind Diagnostic Buttons for this IP
  const pingBtn = $("#drawerPingBtn");
  const traceBtn = $("#drawerTraceBtn");
  const diagBox = $("#drawerDiagOutput");

  if (diagBox) diagBox.innerHTML = '<span class="muted">Click Test Ping or Run Traceroute to diagnose path to this global endpoint…</span>';

  if (pingBtn) {
    pingBtn.onclick = async () => {
      diagBox.innerHTML = `<span class="muted">Pinging ${d.ip}…</span>`;
      try {
        const res = await api(`/api/ping?ip=${encodeURIComponent(d.ip)}`);
        if (res.alive) {
          diagBox.innerHTML = `<span style="color:#34d399;font-weight:700">✓ Host is ALIVE</span>\nRTT: <b>${res.rtt_ms} ms</b>\nPacket Loss: <b>${res.packet_loss_pct}%</b>\nSent: ${res.packets_sent} | Received: ${res.packets_received}`;
        } else {
          diagBox.innerHTML = `<span style="color:#f87171;font-weight:700">✗ Host unreachable or ICMP blocked</span>\nLoss: 100%`;
        }
      } catch (e) {
        diagBox.innerHTML = `<span class="err">Ping error: ${esc(e.message)}</span>`;
      }
    };
  }

  if (traceBtn) {
    traceBtn.onclick = async () => {
      diagBox.innerHTML = `<span class="muted">Running Traceroute to ${d.ip} (max 15 hops)…</span>`;
      try {
        const res = await api(`/api/traceroute?host=${encodeURIComponent(d.ip)}`);
        const hops = res.hops || [];
        if (!hops.length) {
          diagBox.innerHTML = '<span class="muted">Traceroute complete: Destination reached directly or no intermediary hops reported.</span>';
          return;
        }
        diagBox.innerHTML = hops.map(h => `
          <div style="display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.05);padding:2px 0">
            <span>Hop #${h.hop} · <b>${esc(h.ip || "*")}</b> ${h.host ? `<small class="muted">(${esc(h.host)})</small>` : ""}</span>
            <span style="color:var(--accent);font-weight:700">${h.rtt_ms ? h.rtt_ms + " ms" : "*"}</span>
          </div>
        `).join("");
      } catch (e) {
        diagBox.innerHTML = `<span class="err">Traceroute error: ${esc(e.message)}</span>`;
      }
    };
  }
}

function closeGeoDrawer() {
  const drawer = $("#geoEndpointDrawer");
  if (drawer) drawer.hidden = true;
}

function getFlagEmoji(countryCode) {
  if (!countryCode || countryCode.length !== 2) return "🌐";
  const codePoints = countryCode
    .toUpperCase()
    .split("")
    .map(char => 127397 + char.charCodeAt());
  return String.fromCodePoint(...codePoints);
}

/* ---------- cyber noc wallboard data binder ---------- */
async function updateNocWallboard() {
  if ($("#nocWallboard")?.hidden) return;
  try {
    const [tr, tt, sec, topo, geo] = await Promise.all([
      api("/api/traffic"), api("/api/top-talkers?n=6"),
      api("/api/security/audit").catch(()=>({})),
      api("/api/topology"),
      api("/api/geomap").catch(()=>({}))
    ]);

    const s = tr.sample || {};
    const totalMbps = (((s.rx_bps || 0) + (s.tx_bps || 0)) * 8 / (1024 * 1024)).toFixed(1);
    if ($("#nocThroughputTotal")) $("#nocThroughputTotal").textContent = `${totalMbps} Mbps`;
    if ($("#nocRxVal")) $("#nocRxVal").textContent = fmtBps(s.rx_bps);
    if ($("#nocTxVal")) $("#nocTxVal").textContent = fmtBps(s.tx_bps);

    // Chart
    const svg = $("#nocBwChart");
    if (svg && tr.history && tr.history.length > 1) {
      const hist = tr.history;
      const W = 400, H = 80, pad = 4;
      const max = Math.max(1, ...hist.map(p => Math.max(p.rx_bps, p.tx_bps)));
      const x = i => pad + (i / (hist.length - 1)) * (W - pad * 2);
      const y = v => H - pad - (v / max) * (H - pad * 2);
      const path = (k) => hist.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p[k]).toFixed(1)}`).join(" ");
      svg.innerHTML = `<path d="${path("rx_bps")}" fill="none" stroke="#38bdf8" stroke-width="2.5"/><path d="${path("tx_bps")}" fill="none" stroke="#34d399" stroke-width="2.5"/>`;
    }

    // Security
    if (sec) {
      if ($("#nocSecGrade")) $("#nocSecGrade").textContent = sec.grade || "A+";
      if ($("#nocThreatCount")) $("#nocThreatCount").textContent = (sec.findings || []).filter(f => f.severity === "critical" || f.severity === "high").length;
      if ($("#nocOpenPortsCount")) $("#nocOpenPortsCount").textContent = sec.open_ports_count || 0;
      if ($("#nocActiveSocketsCount")) $("#nocActiveSocketsCount").textContent = sec.total_sockets || 0;
      if ($("#nocThreatChips")) {
        $("#nocThreatChips").innerHTML = (sec.findings || []).slice(0, 4).map(f =>
          `<span class="ai-exp-chip ${f.severity === 'critical' ? 'err' : f.severity === 'high' ? 'warn' : 'ok'}">${esc(f.title)}</span>`
        ).join("") || '<span class="ai-exp-chip ok">🛡️ No Critical Vulnerabilities Detected</span>';
      }
    }

    // Gateway & devices
    if (topo) {
      if ($("#nocGwIp")) $("#nocGwIp").textContent = topo.gateway || "—";
      if ($("#nocExtIp")) $("#nocExtIp").textContent = (geo && geo.origin && geo.origin.ip) || topo.self_ip || "—";
      if ($("#nocDevCount")) $("#nocDevCount").textContent = `${topo.nodes.filter(n => n.kind === "device").length} Online`;
      if ($("#nocDevList")) {
        $("#nocDevList").innerHTML = topo.nodes.filter(n => n.kind === "device").slice(0, 6).map(n => `
          <div style="display:flex;justify-content:space-between;font-size:11.5px;padding:3px 6px;background:rgba(255,255,255,0.03);border-radius:4px">
            <span><b>${esc(n.ip)}</b> <small class="muted">(${esc(n.vendor || n.label)})</small></span>
            <span class="badge ${n.reachable ? 'b-yes' : 'b-no'}" style="font-size:9.5px">${n.reachable ? 'ONLINE' : 'OFFLINE'}</span>
          </div>
        `).join("");
      }
    }

    // Top talkers
    if (tt && tt.top && $("#nocTopTalkersList")) {
      $("#nocTopTalkersList").innerHTML = tt.top.slice(0, 5).map(p => `
        <div style="display:flex;justify-content:space-between;font-size:11.5px;padding:3px 6px;background:rgba(255,255,255,0.03);border-radius:4px">
          <span>📦 <b>${esc(p.process)}</b></span>
          <span style="color:var(--accent);font-weight:700">${p.established} est</span>
        </div>
      `).join("");
    }

    // Geo
    if (geo && geo.destinations && $("#nocGeoDestList")) {
      $("#nocGeoCount").textContent = `${(geo.destinations || []).length} Endpoints`;
      $("#nocGeoDestList").innerHTML = geo.destinations.slice(0, 5).map(d => `
        <div style="display:flex;justify-content:space-between;font-size:11.5px;padding:3px 6px;background:rgba(255,255,255,0.03);border-radius:4px">
          <span>${getFlagEmoji(d.country_code)} <b>${esc(d.city || d.ip)}</b> <small class="muted">(${esc(d.country || 'Global')})</small></span>
          <span class="badge b-this" style="font-size:9.5px">${esc(d.cloud_provider || d.category || 'Direct')}</span>
        </div>
      `).join("");
    }
  } catch(e) {}
}

/* ---------- boot ---------- */
async function loadAll() {
  await Promise.allSettled([
    loadOverview(), loadTopology(), loadDevices(),
    loadConnections(), loadRoutes(), loadInterfaces(), loadRaw(),
    loadSecurityAudit(), loadWifi(), loadDnsPresets(), loadNetProfiles(),
    loadHostsStatus(), loadExplainer(), loadGeoMap(),
  ]);
  loadLive();
  startLive();
}
window.addEventListener("resize", () => {
  const t = $("#topoSvg")?.innerHTML;
  loadTopology();
  if (geoMap) geoMap.invalidateSize();
});

(async function boot() {
  try {
    await loadAll();
    setStatus(true);
  } catch (e) {
    setStatus(false, "server unreachable");
  }
  // auto-refresh overview + connections + explainer every 30s (live panel polls every 2s)
  setInterval(() => { loadOverview(); loadConnections(); loadExplainer(); }, 30000);
})();

const refreshSvcLatBtn = $("#refreshSvcLatBtn");
const svcLatencyMatrix = $("#svcLatencyMatrix");
if (refreshSvcLatBtn && svcLatencyMatrix) {
  refreshSvcLatBtn.onclick = async () => {
    refreshSvcLatBtn.disabled = true;
    refreshSvcLatBtn.textContent = "Checking...";
    svcLatencyMatrix.innerHTML = `<span class="muted">Pinging global services...</span>`;
    try {
      const res = await api("/api/service-latency");
      if (res && res.services) {
        svcLatencyMatrix.innerHTML = res.services.map(s => `
          <div style="display:flex;justify-content:space-between;background:rgba(0,0,0,0.2);padding:4px 8px;border-radius:4px">
            <span>${esc(s.name)} <small class="muted">(${esc(s.ip)})</small></span>
            <b>${s.reachable ? `<span style="color:#34d399">${s.ms} ms</span>` : '<span style="color:#f87171">DOWN</span>'}</b>
          </div>
        `).join("");
      }
    } catch (e) {
      svcLatencyMatrix.innerHTML = `<span style="color:#f87171">Error checking services.</span>`;
    }
    refreshSvcLatBtn.disabled = false;
    refreshSvcLatBtn.textContent = "⟳ Check";
  };
}

/* ========================================================================= */
/* CYBER AI INTELLIGENCE HUB & MULTI-PROVIDER CONTROLLER                     */
/* ========================================================================= */
const AI_PROVIDERS = {
  ollama: {
    name: "Ollama (Local LLM)",
    endpoint: "http://localhost:11434/api/generate",
    models: ["gemma4:12b", "gemma4:31b", "llama3", "llama3.1", "mistral", "qwen3-coder-next:latest", "qwen3.6:latest"],
    needsKey: false,
    badge: "🦙 Ollama (Local)",
    sub: "100% Private Offline"
  },
  lmstudio: {
    name: "LM Studio / LocalAI",
    endpoint: "http://localhost:1234/v1/chat/completions",
    models: ["local-model"],
    needsKey: false,
    badge: "🖥️ LM Studio (Local)",
    sub: "Local OpenAI-Compatible API"
  },
  openai: {
    name: "OpenAI (ChatGPT)",
    endpoint: "https://api.openai.com/v1/chat/completions",
    models: ["gpt-4o", "gpt-4o-mini", "o3-mini", "o1", "gpt-4-turbo"],
    needsKey: true,
    badge: "🟢 OpenAI Cloud",
    sub: "GPT-4o & Reasoning"
  },
  anthropic: {
    name: "Anthropic (Claude)",
    endpoint: "https://api.anthropic.com/v1/messages",
    models: ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
    needsKey: true,
    badge: "🟣 Claude Cloud",
    sub: "Anthropic Reasoning"
  },
  google: {
    name: "Google (Gemini)",
    endpoint: "https://generativelanguage.googleapis.com/v1beta",
    models: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    needsKey: true,
    badge: "🔵 Gemini Cloud",
    sub: "Google Intelligence"
  },
  deepseek: {
    name: "DeepSeek",
    endpoint: "https://api.deepseek.com/chat/completions",
    models: ["deepseek-chat", "deepseek-reasoner"],
    needsKey: true,
    badge: "🐋 DeepSeek Cloud",
    sub: "DeepSeek V3 / R1"
  },
  groq: {
    name: "Groq (Ultra-Fast)",
    endpoint: "https://api.groq.com/openai/v1/chat/completions",
    models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
    needsKey: true,
    badge: "⚡ Groq LPUs",
    sub: "Sub-Second Inference"
  },
  mistral: {
    name: "Mistral AI",
    endpoint: "https://api.mistral.ai/v1/chat/completions",
    models: ["mistral-large-latest", "codestral-latest", "mistral-small-latest"],
    needsKey: true,
    badge: "🌊 Mistral Cloud",
    sub: "European AI Frontier"
  },
  openrouter: {
    name: "OpenRouter",
    endpoint: "https://openrouter.ai/api/v1/chat/completions",
    models: ["meta-llama/llama-3.3-70b-instruct", "anthropic/claude-3.5-sonnet", "google/gemini-2.0-flash-001", "deepseek/deepseek-r1"],
    needsKey: true,
    badge: "🌐 OpenRouter",
    sub: "100+ Models Aggregator"
  },
  custom: {
    name: "Custom / Any AI",
    endpoint: "http://localhost:8000/v1/chat/completions",
    models: ["custom-model"],
    needsKey: true,
    badge: "⚙️ Custom AI",
    sub: "Any OpenAI-Compatible Endpoint"
  }
};

const AI_PERSONAS = {
  threat_hunter: "You are an elite Cyber Threat Hunter and Security Auditor inside NetVisual. Focus on detecting suspicious connections, exposed risky ports, potential C2 beacons, DNS leaks, and anomalous host behavior. Provide crisp, actionable remediation advice.",
  packet_analyst: "You are a Senior Network & Protocol Architect. Analyze network sockets, protocols (TCP, UDP, DNS, TLS, ICMP), latency spikes, packet flows, and routing topology. Explain deep technical concepts clearly.",
  speed_optimizer: "You are a Network Performance & QoS Optimizer. Help diagnose bandwidth bottlenecks, high ping, bufferbloat, jitter, and Wi-Fi interference. Give practical troubleshooting steps.",
  concise: "You are a concise network diagnostics assistant. Provide short, bulleted, highly accurate answers without unnecessary fluff.",
  custom_persona: ""
};

// UI Elements
const aiProviderSelect = $("#aiProvider");
const aiModelSelect = $("#aiModel");
const aiCustomModelInput = $("#aiCustomModelInput");
const aiCustomModelToggle = $("#aiCustomModelToggle");
const aiEndpointInput = $("#aiEndpoint");
const aiResetEndpointBtn = $("#aiResetEndpointBtn");
const aiApiKeyInput = $("#aiApiKey");
const aiKeyGroup = $("#aiKeyGroup");
const aiToggleKeyVisBtn = $("#aiToggleKeyVisBtn");
const aiTestBtn = $("#aiTestBtn");
const aiTestResult = $("#aiTestResult");
const aiActiveEngineLabel = $("#aiActiveEngineLabel");
const aiChatSubLabel = $("#aiChatSubLabel");
const aiSavedIndicator = $("#aiSavedIndicator");
const aiPersonaSelect = $("#aiPersona");
const aiCustomPromptWrap = $("#aiCustomPromptWrap");
const aiCustomSystemPrompt = $("#aiCustomSystemPrompt");
const aiTempSlider = $("#aiTempSlider");
const aiTempDisplay = $("#aiTempDisplay");
const aiIncludeTelemetry = $("#aiIncludeTelemetry");
const aiTelemetryStatusHint = $("#aiTelemetryStatusHint");
const aiToggleAdvBtn = $("#aiToggleAdvBtn");
const aiAdvBody = $("#aiAdvBody");
const aiAdvArrow = $("#aiAdvArrow");
const aiChatHistory = $("#aiChatHistory");
const aiChatInput = $("#aiChatInput");
const aiSendBtn = $("#aiSendBtn");
const aiClearChatBtn = $("#aiClearChatBtn");
const aiCopyChatBtn = $("#aiCopyChatBtn");

let isCustomModelMode = false;

// Persist config to localStorage
function saveAiConfig() {
  const cfg = {
    provider: aiProviderSelect ? aiProviderSelect.value : "ollama",
    isCustomModel: isCustomModelMode,
    model: isCustomModelMode ? (aiCustomModelInput?.value || "") : (aiModelSelect?.value || ""),
    endpoint: aiEndpointInput ? aiEndpointInput.value : "",
    apiKey: aiApiKeyInput ? aiApiKeyInput.value : "",
    persona: aiPersonaSelect ? aiPersonaSelect.value : "threat_hunter",
    customPrompt: aiCustomSystemPrompt ? aiCustomSystemPrompt.value : "",
    temperature: aiTempSlider ? aiTempSlider.value : "0.7",
    includeTelemetry: aiIncludeTelemetry ? aiIncludeTelemetry.checked : true
  };
  try {
    localStorage.setItem("netvisual_ai_config", JSON.stringify(cfg));
    if (aiSavedIndicator) {
      aiSavedIndicator.textContent = "💾 Saved!";
      aiSavedIndicator.style.opacity = "1";
      setTimeout(() => { if (aiSavedIndicator) aiSavedIndicator.style.opacity = "0.7"; }, 1500);
    }
  } catch(e) {}
  updateAiHeaderStatus();
}

function loadAiConfig() {
  try {
    const raw = localStorage.getItem("netvisual_ai_config");
    if (!raw) return;
    const cfg = JSON.parse(raw);
    if (cfg.provider && aiProviderSelect) {
      aiProviderSelect.value = cfg.provider;
      applyProviderSettings(cfg.provider, false);
    }
    if (cfg.endpoint && aiEndpointInput) aiEndpointInput.value = cfg.endpoint;
    if (cfg.apiKey && aiApiKeyInput) aiApiKeyInput.value = cfg.apiKey;
    if (cfg.persona && aiPersonaSelect) {
      aiPersonaSelect.value = cfg.persona;
      if (aiCustomPromptWrap) aiCustomPromptWrap.style.display = cfg.persona === "custom_persona" ? "block" : "none";
    }
    if (cfg.customPrompt && aiCustomSystemPrompt) aiCustomSystemPrompt.value = cfg.customPrompt;
    if (cfg.temperature && aiTempSlider && aiTempDisplay) {
      aiTempSlider.value = cfg.temperature;
      aiTempDisplay.textContent = cfg.temperature;
    }
    if (typeof cfg.includeTelemetry === "boolean" && aiIncludeTelemetry) {
      aiIncludeTelemetry.checked = cfg.includeTelemetry;
      if (aiTelemetryStatusHint) {
        aiTelemetryStatusHint.textContent = cfg.includeTelemetry ? "● Telemetry Attached" : "○ Telemetry Detached";
        aiTelemetryStatusHint.style.color = cfg.includeTelemetry ? "var(--accent)" : "var(--muted)";
      }
    }
    if (cfg.isCustomModel) {
      setCustomModelMode(true);
      if (cfg.model && aiCustomModelInput) aiCustomModelInput.value = cfg.model;
    } else if (cfg.model && aiModelSelect) {
      setCustomModelMode(false);
      // If model option doesn't exist, add it
      if (!Array.from(aiModelSelect.options).some(o => o.value === cfg.model)) {
        const opt = document.createElement("option");
        opt.value = cfg.model;
        opt.textContent = cfg.model;
        aiModelSelect.appendChild(opt);
      }
      aiModelSelect.value = cfg.model;
    }
  } catch(e) {}
  updateAiHeaderStatus();
}

function updateAiHeaderStatus() {
  const pKey = aiProviderSelect ? aiProviderSelect.value : "ollama";
  const pInfo = AI_PROVIDERS[pKey] || AI_PROVIDERS.ollama;
  const currentModel = getActiveModelName();
  if (aiActiveEngineLabel) {
    aiActiveEngineLabel.textContent = `${pInfo.name.split(" ")[0]} · ${currentModel}`;
  }
  if (aiChatSubLabel) {
    const telem = (aiIncludeTelemetry && aiIncludeTelemetry.checked) ? "Telemetry Attached" : "Telemetry Off";
    aiChatSubLabel.textContent = `Provider: ${pInfo.name} · Model: ${currentModel} · ${telem}`;
  }
}

function getActiveModelName() {
  if (isCustomModelMode && aiCustomModelInput && aiCustomModelInput.value.trim()) {
    return aiCustomModelInput.value.trim();
  }
  return aiModelSelect ? aiModelSelect.value : "llama3";
}

function setCustomModelMode(custom) {
  isCustomModelMode = custom;
  if (aiModelSelect && aiCustomModelInput && aiCustomModelToggle) {
    if (custom) {
      aiModelSelect.style.display = "none";
      aiCustomModelInput.style.display = "block";
      aiCustomModelToggle.textContent = "📑 List";
      aiCustomModelToggle.title = "Switch back to dropdown list";
    } else {
      aiModelSelect.style.display = "block";
      aiCustomModelInput.style.display = "none";
      aiCustomModelToggle.textContent = "✏️ Custom";
      aiCustomModelToggle.title = "Switch to manual model name typing";
    }
  }
}

function applyProviderSettings(providerKey, resetDefaults = true) {
  const info = AI_PROVIDERS[providerKey] || AI_PROVIDERS.custom;
  
  // Show / Hide API Key
  if (aiKeyGroup) {
    aiKeyGroup.style.display = info.needsKey ? "flex" : "none";
  }

  // Populate models dropdown
  if (resetDefaults && aiModelSelect) {
    aiModelSelect.innerHTML = info.models.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
    if (info.models.length > 0) aiModelSelect.value = info.models[0];
    setCustomModelMode(false);
  }

  // Endpoint
  if (resetDefaults && aiEndpointInput) {
    aiEndpointInput.value = info.endpoint;
  }

  // If custom provider, automatically default to custom model mode
  if (providerKey === "custom" && resetDefaults) {
    setCustomModelMode(true);
    if (aiCustomModelInput) aiCustomModelInput.value = "my-custom-model";
  }

  if (aiTestResult) aiTestResult.innerHTML = "";
  updateAiHeaderStatus();
  saveAiConfig();
}

// Event Listeners
if (aiProviderSelect) {
  aiProviderSelect.addEventListener("change", () => {
    applyProviderSettings(aiProviderSelect.value, true);
  });
}

if (aiModelSelect) {
  aiModelSelect.addEventListener("change", () => {
    saveAiConfig();
  });
}

if (aiCustomModelInput) {
  aiCustomModelInput.addEventListener("input", () => {
    saveAiConfig();
  });
}

if (aiCustomModelToggle) {
  aiCustomModelToggle.addEventListener("click", () => {
    setCustomModelMode(!isCustomModelMode);
    saveAiConfig();
  });
}

if (aiResetEndpointBtn && aiEndpointInput) {
  aiResetEndpointBtn.addEventListener("click", () => {
    const pKey = aiProviderSelect ? aiProviderSelect.value : "ollama";
    const info = AI_PROVIDERS[pKey] || AI_PROVIDERS.ollama;
    aiEndpointInput.value = info.endpoint;
    saveAiConfig();
  });
}

if (aiEndpointInput) {
  aiEndpointInput.addEventListener("input", saveAiConfig);
}

if (aiApiKeyInput) {
  aiApiKeyInput.addEventListener("input", saveAiConfig);
}

if (aiToggleKeyVisBtn && aiApiKeyInput) {
  aiToggleKeyVisBtn.addEventListener("click", () => {
    aiApiKeyInput.type = aiApiKeyInput.type === "password" ? "text" : "password";
    aiToggleKeyVisBtn.textContent = aiApiKeyInput.type === "password" ? "👁️" : "🙈";
  });
}

// Persona selection
if (aiPersonaSelect) {
  aiPersonaSelect.addEventListener("change", () => {
    if (aiCustomPromptWrap) {
      aiCustomPromptWrap.style.display = aiPersonaSelect.value === "custom_persona" ? "block" : "none";
    }
    saveAiConfig();
  });
}

if (aiCustomSystemPrompt) {
  aiCustomSystemPrompt.addEventListener("input", saveAiConfig);
}

// Temperature slider
if (aiTempSlider && aiTempDisplay) {
  aiTempSlider.addEventListener("input", () => {
    aiTempDisplay.textContent = aiTempSlider.value;
    saveAiConfig();
  });
}

// Telemetry checkbox
if (aiIncludeTelemetry) {
  aiIncludeTelemetry.addEventListener("change", () => {
    if (aiTelemetryStatusHint) {
      aiTelemetryStatusHint.textContent = aiIncludeTelemetry.checked ? "● Telemetry Attached" : "○ Telemetry Detached";
      aiTelemetryStatusHint.style.color = aiIncludeTelemetry.checked ? "var(--accent)" : "var(--muted)";
    }
    updateAiHeaderStatus();
    saveAiConfig();
  });
}

// Advanced accordion toggle
if (aiToggleAdvBtn && aiAdvBody) {
  aiToggleAdvBtn.addEventListener("click", () => {
    const isHidden = aiAdvBody.style.display === "none";
    aiAdvBody.style.display = isHidden ? "flex" : "none";
    if (aiAdvArrow) aiAdvArrow.textContent = isHidden ? "▲" : "▼";
  });
  // Default collapsed
  aiAdvBody.style.display = "none";
}

// Test Connection & Discover Models
if (aiTestBtn) {
  aiTestBtn.addEventListener("click", async () => {
    aiTestBtn.disabled = true;
    aiTestBtn.textContent = "⏳ Testing Connection...";
    aiTestResult.innerHTML = `<span style="color:var(--accent)">Contacting engine...</span>`;
    
    const payload = {
      provider: aiProviderSelect.value,
      endpoint: aiEndpointInput.value.trim(),
      api_key: aiApiKeyInput.value.trim()
    };
    
    try {
      const res = await api("/api/ai/test", { method: "POST", body: JSON.stringify(payload) });
      if (res && res.success) {
        aiTestResult.innerHTML = `<span style="color:#34d399">✅ ${esc(res.message)}</span>`;
        if (res.models && res.models.length > 0) {
          aiModelSelect.innerHTML = res.models.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
          aiModelSelect.value = res.models[0];
          setCustomModelMode(false);
          aiTestResult.innerHTML += `<br><span style="color:#38bdf8;font-size:11px">Populated ${res.models.length} discovered models!</span>`;
        }
      } else {
        const msg = (res && res.message) ? res.message : "Connection failed.";
        aiTestResult.innerHTML = `<span style="color:#f87171">❌ ${esc(msg)}</span>`;
      }
    } catch (e) {
      aiTestResult.innerHTML = `<span style="color:#f87171">❌ Request failed: ${esc(e.message)}</span>`;
    } finally {
      aiTestBtn.disabled = false;
      aiTestBtn.textContent = "🔌 Test & Discover Models";
      updateAiHeaderStatus();
      saveAiConfig();
    }
  });
}

// Quick Suggestion Chips
document.querySelectorAll(".ai-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const prompt = chip.dataset.prompt;
    if (prompt && aiChatInput) {
      aiChatInput.value = prompt;
      sendAiMessage();
    }
  });
});

// Clear Chat
if (aiClearChatBtn && aiChatHistory) {
  aiClearChatBtn.addEventListener("click", () => {
    if (!confirm("Clear this chat conversation?")) return;
    aiChatHistory.innerHTML = `
      <div class="ai-welcome-box">
        <div class="ai-welcome-icon">⚡</div>
        <h3 style="margin-bottom:6px;font-size:18px;color:var(--txt);">NetVisual Cyber AI Assistant</h3>
        <p style="color:var(--muted);font-size:13px;max-width:520px;line-height:1.5;margin-bottom:16px;">
          Your dedicated cybersecurity and network intelligence co-pilot. Query real-time traffic, diagnose packet anomalies, inspect risky sockets, or chat with local and cloud AI models.
        </p>
        <div class="ai-welcome-tags">
          <span>🔒 100% Private Local Ollama</span>
          <span>⚡ Live Telemetry Injection</span>
          <span>🌐 Multi-Provider Ready</span>
        </div>
      </div>
    `;
  });
}

// Copy full conversation
if (aiCopyChatBtn && aiChatHistory) {
  aiCopyChatBtn.addEventListener("click", () => {
    const text = Array.from(aiChatHistory.children)
      .map(el => {
        if (el.classList.contains("ai-msg-user")) return `[USER]:\n${el.innerText.trim()}\n`;
        if (el.classList.contains("ai-msg-bot")) return `[CYBER AI]:\n${el.innerText.trim()}\n`;
        return "";
      })
      .filter(Boolean)
      .join("\n--------------------\n\n");
    
    if (!text) {
      alert("No chat messages to copy.");
      return;
    }
    navigator.clipboard.writeText(text).then(() => {
      const orig = aiCopyChatBtn.textContent;
      aiCopyChatBtn.textContent = "✅ Copied!";
      setTimeout(() => { aiCopyChatBtn.textContent = orig; }, 1800);
    });
  });
}

function isHebrew(text) {
  return /[\u0590-\u05FF]/.test(text);
}

// Format Markdown inside AI messages with full BiDi & RTL Support
function formatAiResponse(raw) {
  let text = esc(raw);

  // Triple backtick code blocks (strictly LTR)
  text = text.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
    const codeId = "code-" + Math.random().toString(36).substring(2, 9);
    return `
      <div class="ai-code-block" dir="ltr">
        <div class="ai-code-header">
          <span>${esc(lang || 'code')}</span>
          <button class="ai-copy-btn" onclick="copySnippet('${codeId}')">📋 Copy Code</button>
        </div>
        <pre class="ai-code-content" id="${codeId}">${code.trim()}</pre>
      </div>
    `;
  });

  // Single backtick inline code -> isolate with <bdi dir="ltr">
  text = text.replace(/`([^`]+)`/g, '<bdi dir="ltr"><code class="ai-inline-code">$1</code></bdi>');

  // Standalone IP addresses & port pairs (e.g. 192.168.1.1 or 10.0.0.1:443) -> isolate LTR so they don't reverse
  text = text.replace(/(^|[\s(,;])((?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::[0-9]+)?)(?=$|[\s),;.?!])/g, '$1<bdi dir="ltr" class="ai-tech-val">$2</bdi>');

  // Bold text: isolate with <bdi>
  text = text.replace(/\*\*([^*]+)\*\*/g, '<bdi><strong class="ai-bold">$1</strong></bdi>');

  // Headers (###, ##, #)
  text = text.replace(/^###[ \t]+(.+)$/gm, '<h5 dir="auto" style="margin:8px 0 4px;color:var(--accent);">$1</h5>');
  text = text.replace(/^##[ \t]+(.+)$/gm, '<h4 dir="auto" style="margin:10px 0 4px;color:var(--txt);">$1</h4>');

  // Bullet points with dir="auto"
  text = text.replace(/^[ \t]*[-*][ \t]+(.+)$/gm, '<li dir="auto" class="ai-list-item">$1</li>');

  // Line breaks
  text = text.replace(/\n/g, '<br/>');

  return `<div dir="auto" class="ai-formatted-text">${text}</div>`;
}

// Global snippet copy handler
window.copySnippet = function(id) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => {
    event.target.textContent = "✅ Copied!";
    setTimeout(() => { event.target.textContent = "📋 Copy Code"; }, 1600);
  });
};

window.copyMessageText = function(btn) {
  const container = btn.closest(".ai-msg-bot");
  if (!container) return;
  const content = container.querySelector(".ai-msg-content");
  if (!content) return;
  navigator.clipboard.writeText(content.innerText).then(() => {
    btn.textContent = "✅ Copied!";
    setTimeout(() => { btn.textContent = "📋 Copy"; }, 1600);
  });
};

// Send AI Message Function
async function sendAiMessage() {
  const prompt = aiChatInput ? aiChatInput.value.trim() : "";
  if (!prompt) return;
  
  // Clear welcome box if present
  const welcome = aiChatHistory.querySelector(".ai-welcome-box");
  if (welcome) welcome.remove();
  
  const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const userIsRtl = isHebrew(prompt);
  const userDir = userIsRtl ? 'dir="rtl"' : 'dir="ltr"';

  // Append User message
  aiChatHistory.innerHTML += `
    <div class="ai-msg-user" ${userDir}>
      <div style="font-size:10.5px;color:rgba(0,0,0,0.6);margin-bottom:4px;font-weight:700;display:flex;justify-content:space-between;direction:ltr;">
        <span>👤 You</span>
        <span>${timestamp}</span>
      </div>
      <div dir="auto" style="unicode-bidi:plaintext;text-align:start;">${esc(prompt)}</div>
    </div>
  `;
  
  aiChatInput.value = "";
  aiChatInput.style.height = "auto";
  aiSendBtn.disabled = true;
  aiSendBtn.innerHTML = `<span>Working...</span><span class="spinner" style="display:inline-block;width:12px;height:12px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite"></span>`;
  aiChatHistory.scrollTop = aiChatHistory.scrollHeight;
  
  const provider = aiProviderSelect ? aiProviderSelect.value : "ollama";
  const modelName = getActiveModelName();
  const personaKey = aiPersonaSelect ? aiPersonaSelect.value : "threat_hunter";
  const customSys = personaKey === "custom_persona" ? (aiCustomSystemPrompt?.value || "") : (AI_PERSONAS[personaKey] || "");

  const loadingId = "ai-loading-" + Date.now();
  aiChatHistory.innerHTML += `
    <div id="${loadingId}" class="ai-msg-bot" style="display:flex;align-items:center;gap:10px;color:var(--muted);">
      <span style="display:inline-block;width:14px;height:14px;border:2px solid var(--accent);border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite"></span>
      <span><b>Cyber AI</b> is analyzing telemetry with <b>${esc(modelName)}</b>...</span>
    </div>
  `;
  aiChatHistory.scrollTop = aiChatHistory.scrollHeight;
  
  try {
    const payload = {
      provider: provider,
      model: modelName,
      api_key: aiApiKeyInput ? aiApiKeyInput.value.trim() : "",
      endpoint: aiEndpointInput ? aiEndpointInput.value.trim() : "",
      prompt: prompt,
      system_prompt: customSys,
      temperature: aiTempSlider ? parseFloat(aiTempSlider.value) : 0.7,
      include_context: aiIncludeTelemetry ? aiIncludeTelemetry.checked : true
    };

    const res = await api("/api/ai/chat", { method: "POST", body: JSON.stringify(payload) });
    const bubble = $(`#${loadingId}`);
    
    if (res && res.reply) {
      const formatted = formatAiResponse(res.reply);
      
      let actionBadgeHtml = "";
      if (res.action_executed) {
        const act = res.action_executed;
        const toolLabel = esc(act.tool || "Action");
        const argsStr = act.args ? esc(JSON.stringify(act.args)) : "";
        const isSearch = act.tool === "search_web";
        const icon = isSearch ? "🌐" : "⚡";
        const titleText = isSearch ? "Live Web Search Executed" : "System Tool Executed";
        
        actionBadgeHtml = `
          <div class="ai-action-card" dir="ltr">
            <div class="ai-action-header">
              <span class="ai-action-icon">${icon}</span>
              <span class="ai-action-title"><b>${titleText}:</b> <code>${toolLabel}</code></span>
              <span class="ai-action-status">✅ Completed</span>
            </div>
            ${argsStr && argsStr !== "{}" ? `<div class="ai-action-args">Parameters: <span>${argsStr}</span></div>` : ""}
          </div>
        `;
      }

      const botHtml = `
        <div class="ai-msg-bot">
          <div class="ai-msg-header">
            <div class="ai-msg-tag">
              <span>🤖 Cyber AI</span>
              <span style="font-size:10px;opacity:0.6;font-weight:normal">(${esc(modelName)})</span>
            </div>
            <div class="ai-msg-actions">
              <span style="font-size:10.5px;color:var(--muted)">${timestamp}</span>
              <button class="ai-copy-btn" onclick="copyMessageText(this)">📋 Copy</button>
            </div>
          </div>
          ${actionBadgeHtml}
          <div class="ai-msg-content">${formatted}</div>
        </div>
      `;
      if (bubble) bubble.outerHTML = botHtml;
      else aiChatHistory.innerHTML += botHtml;
    } else {
      const errMsg = (res && res.error) ? res.error : "No reply received from model.";
      const errHtml = `
        <div class="ai-msg-bot" style="background:rgba(239,68,68,0.1);border-color:#ef4444;color:#fca5a5;">
          <div class="ai-msg-header" style="border-color:rgba(239,68,68,0.2);">
            <div class="ai-msg-tag" style="color:#ef4444;">⚠️ Model Error</div>
            <span style="font-size:10.5px;color:var(--muted)">${timestamp}</span>
          </div>
          <div>${esc(errMsg)}</div>
        </div>
      `;
      if (bubble) bubble.outerHTML = errHtml;
      else aiChatHistory.innerHTML += errHtml;
    }
  } catch (err) {
    const bubble = $(`#${loadingId}`);
    const errHtml = `
      <div class="ai-msg-bot" style="background:rgba(239,68,68,0.1);border-color:#ef4444;color:#fca5a5;">
        <div class="ai-msg-header" style="border-color:rgba(239,68,68,0.2);">
          <div class="ai-msg-tag" style="color:#ef4444;">⚠️ Network/Client Error</div>
          <span style="font-size:10.5px;color:var(--muted)">${timestamp}</span>
        </div>
        <div>${esc(err.message)}</div>
      </div>
    `;
    if (bubble) bubble.outerHTML = errHtml;
    else aiChatHistory.innerHTML += errHtml;
  } finally {
    aiSendBtn.disabled = false;
    aiSendBtn.innerHTML = `<span>Send</span><span style="font-size:15px">🚀</span>`;
    aiChatHistory.scrollTop = aiChatHistory.scrollHeight;
  }
}

if (aiSendBtn) {
  aiSendBtn.addEventListener("click", sendAiMessage);
}

if (aiChatInput) {
  aiChatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendAiMessage();
    }
  });

  // Auto-grow textarea
  aiChatInput.addEventListener("input", () => {
    aiChatInput.style.height = "auto";
    aiChatInput.style.height = Math.min(aiChatInput.scrollHeight, 130) + "px";
  });
}

// Initial configuration restore on script load
loadAiConfig();

