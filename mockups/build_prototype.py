"""Assemble the .dc.html mockup screens into a clickable prototype page.

Each screen shows one at a time inside a scaled frame; buttons that exist in
the real flow navigate to their target screen (wired by exact visible text).
Output: onboarding-prototype.html
"""

import json
import re
import pathlib

SCREENS = [
    # id, file, sidebar label, sublabel
    ("create-app", "CreateApplication.dc.html", "Create & invite", "Service Mgmt · day 0"),
    ("app-form", "ApplicationForm.dc.html", "Application form", "Member · day 1"),
    ("doc-upload", "DocumentUpload.dc.html", "Supporting documents", "Member · day 1"),
    ("review-submit", "ReviewSubmit.dc.html", "Review & submit", "Member · day 2"),
    ("member-status", "Main.dc.html", "Status & clarifications", "Member · day 6"),
    ("ops-queue", "OpsQueue.dc.html", "Queue", "Operations"),
    ("ops-detail", "ApplicationDetail.dc.html", "Application detail", "Operations"),
    ("compliance-review", "ComplianceReview.dc.html", "Review & decision", "Compliance"),
    ("provisioning", "Provisioning.dc.html", "Provisioning", "Technology"),
    ("member-live", "MemberLive.dc.html", "Live on the exchange", "Member · day 28"),
    ("pipeline", "Pipeline.dc.html", "Pipeline & metrics", "Service Mgmt"),
]

MEMBER_IDS = {"create-app", "app-form", "doc-upload", "review-submit", "member-status"}

# exact visible text -> target screen id
CLICK_MAP = {
    "Send invitation →": "app-form",
    "Continue to documents →": "doc-upload",
    "← Back to form": "app-form",
    "Review & submit": "review-submit",
    "Supporting documents": "doc-upload",
    "Submit application": "member-status",
    "← Back to documents": "doc-upload",
    "Review pack": "ops-detail",
    "Open": "ops-detail",
    "Route query": "ops-detail",
    "Send to KYC": "ops-detail",
    "View": "ops-detail",
    "Queue": "ops-queue",
    "Pipeline": "pipeline",
    "New application": "create-app",
    "Review queue": "compliance-review",
    "Provisioning tasks": "provisioning",
    "Record decision": "provisioning",
    "Request information via Ops": "ops-detail",
    "Mark member live": "member-live",
}

here = pathlib.Path(__file__).parent
frames = []
for sid, fname, label, sub in SCREENS:
    src = (here / fname).read_text()
    body = re.search(r"<x-dc>(.*)</x-dc>", src, re.S).group(1)
    body = re.sub(r"<helmet>.*?</helmet>", "", body, flags=re.S).strip()
    frames.append(f'<div class="screen" id="screen-{sid}">{body}</div>')

nav_member = "".join(
    f'<div class="navitem" data-target="{sid}"><span class="n">{i}</span>'
    f'<span><b>{label}</b><i>{sub}</i></span></div>'
    for i, (sid, _, label, sub) in enumerate(SCREENS, 1) if sid in MEMBER_IDS
)
nav_internal = "".join(
    f'<div class="navitem" data-target="{sid}"><span class="n">{i}</span>'
    f'<span><b>{label}</b><i>{sub}</i></span></div>'
    for i, (sid, _, label, sub) in enumerate(SCREENS, 1) if sid not in MEMBER_IDS
)
order = json.dumps([s[0] for s in SCREENS])
click_map = json.dumps(CLICK_MAP, ensure_ascii=False)

page = '''<meta charset="utf-8">
<title>Exchange Onboarding Prototype</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  body { margin: 0; background: #e9e7e2; color: #1a2332; overflow: hidden;
         font-family: "IBM Plex Sans", -apple-system, sans-serif; }
  .h { font-family: "Schibsted Grotesk", sans-serif; }
  .mono { font-family: "IBM Plex Mono", monospace; }
  td { padding: 13px 16px; border-bottom: 1px solid #eeece7; font-size: 13.5px; vertical-align: middle; }
  th { padding: 9px 16px; text-align: left; font-family: "IBM Plex Mono", monospace; font-weight: 500; font-size: 11px; letter-spacing: 0.09em; text-transform: uppercase; color: #8b95a5; border-bottom: 1px solid #d8d4cc; }
  .seg { height: 10px; border-radius: 3px; }
  .lbl { font-size: 12px; font-weight: 600; color: #37404f; margin-bottom: 5px; }
  .inp { border: 1px solid #d8d4cc; border-radius: 6px; background: #ffffff; padding: 9px 12px; font-size: 13.5px; }
  .ph { color: #a7ada2; }
  .kv { display: flex; justify-content: space-between; gap: 16px; font-size: 13px; padding: 6px 0; }
  .kv .k { color: #8b95a5; }
  .kv .v { font-weight: 500; text-align: right; }
  .docrow { display: flex; align-items: center; gap: 9px; font-size: 12.5px; padding: 4px 0; }
  a { color: #c0392f; }

  .app { display: flex; height: 100vh; }
  .side { width: 250px; flex-shrink: 0; background: #1a2332; color: #ffffff;
          display: flex; flex-direction: column; padding: 20px 0 14px; overflow-y: auto; }
  .side .brand { padding: 0 20px 14px; border-bottom: 1px solid #2b3444; }
  .side .brand .t { font-family: "Schibsted Grotesk", sans-serif; font-weight: 700; font-size: 15px; }
  .side .brand .s { font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: 0.12em;
                    text-transform: uppercase; color: #8b95a5; margin-top: 3px; }
  .grouplabel { font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: 0.12em;
                text-transform: uppercase; color: #6c7686; padding: 16px 20px 6px; }
  .navitem { display: flex; gap: 10px; align-items: flex-start; padding: 8px 20px; cursor: pointer; }
  .navitem:hover { background: #232d3e; }
  .navitem.active { background: #2b3444; box-shadow: inset 3px 0 0 #e0685c; }
  .navitem .n { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: #e0685c; padding-top: 2px; width: 14px; }
  .navitem b { display: block; font-size: 13px; font-weight: 600; }
  .navitem i { display: block; font-style: normal; font-size: 11px; color: #8b95a5; margin-top: 1px; }
  .side .hint { margin-top: auto; padding: 14px 20px 0; font-size: 11.5px; color: #8b95a5; line-height: 1.5;
                border-top: 1px solid #2b3444; }

  .main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .topbar { display: flex; align-items: center; justify-content: space-between;
            padding: 12px 22px; }
  .topbar .crumb { font-size: 13.5px; color: #5a6473; }
  .topbar .crumb b { color: #1a2332; font-weight: 600; }
  .topbar .btns { display: flex; gap: 8px; }
  .navbtn { border: 1px solid #d5d1c9; background: #ffffff; border-radius: 6px; padding: 6px 14px;
            font: inherit; font-size: 13px; font-weight: 600; color: #37404f; cursor: pointer; }
  .navbtn:hover { border-color: #b8b2a7; }
  .navbtn:focus-visible, .navitem:focus-visible { outline: 2px solid #c0392f; outline-offset: 2px; }

  .stage { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; padding: 0 22px 18px; }
  .frame { border-radius: 10px; overflow: hidden; border: 1px solid #d5d1c9; flex-shrink: 0;
           box-shadow: 0 14px 36px rgba(26,35,50,0.13); background: #f4f3f0; }
  .screen { width: 1440px; height: 900px; transform-origin: top left; display: none; }
  .screen.on { display: block; }

  .proto-link { cursor: pointer; position: relative; }
  .proto-link:hover { outline: 2px solid rgba(192,57,47,0.55); outline-offset: 2px; border-radius: 6px; }
</style>
<div class="app">
  <div class="side">
    <div class="brand">
      <div class="t">Exchange · Member Onboarding</div>
      <div class="s">Clickable prototype · v1</div>
    </div>
    <div class="grouplabel">Member journey</div>
''' + nav_member + '''
    <div class="grouplabel">Inside the exchange</div>
''' + nav_internal + '''
    <div class="hint">Anything that glows on hover is wired to the real flow — click it. Use ← → keys or the Back / Next buttons to step through the walkthrough.</div>
  </div>
  <div class="main">
    <div class="topbar">
      <div class="crumb" id="crumb"></div>
      <div class="btns">
        <button class="navbtn" id="prev" type="button">← Back</button>
        <button class="navbtn" id="next" type="button">Next →</button>
      </div>
    </div>
    <div class="stage"><div class="frame" id="frame">
''' + "\n".join(frames) + '''
    </div></div>
  </div>
</div>
<script>
  var ORDER = ''' + order + ''';
  var CLICKS = ''' + click_map + ''';
  var LABELS = {};
  document.querySelectorAll(".navitem").forEach(function (it) {
    LABELS[it.dataset.target] = it.querySelector("b").textContent + " — " + it.querySelector("i").textContent;
    it.setAttribute("tabindex", "0");
    it.addEventListener("click", function () { show(it.dataset.target); });
  });

  var current = ORDER[0];
  function show(id) {
    current = id;
    document.querySelectorAll(".screen").forEach(function (s) { s.classList.toggle("on", s.id === "screen-" + id); });
    document.querySelectorAll(".navitem").forEach(function (it) { it.classList.toggle("active", it.dataset.target === id); });
    var idx = ORDER.indexOf(id);
    document.getElementById("crumb").innerHTML = "<b>" + (idx + 1) + " / " + ORDER.length + "</b> &nbsp; " + LABELS[id];
    fit();
  }
  function step(d) {
    var idx = ORDER.indexOf(current) + d;
    if (idx >= 0 && idx < ORDER.length) show(ORDER[idx]);
  }
  document.getElementById("prev").addEventListener("click", function () { step(-1); });
  document.getElementById("next").addEventListener("click", function () { step(1); });
  addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") step(-1);
    if (e.key === "ArrowRight") step(1);
  });

  function fit() {
    var stage = document.querySelector(".stage");
    var s = Math.min((stage.clientWidth - 50) / 1440, (stage.clientHeight - 22) / 900, 1);
    var frame = document.getElementById("frame");
    frame.style.width = (1440 * s) + "px";
    frame.style.height = (900 * s) + "px";
    document.querySelectorAll(".screen").forEach(function (sc) { sc.style.transform = "scale(" + s + ")"; });
  }
  addEventListener("resize", fit);

  // Wire clicks by exact visible text; innermost matching element wins.
  var all = document.querySelectorAll(".screen div, .screen span");
  all.forEach(function (el) {
    var t = el.textContent.replace(/\\s+/g, " ").trim();
    var target = CLICKS[t];
    if (!target) return;
    var inner = false;
    el.querySelectorAll("div, span").forEach(function (c) {
      if (c.textContent.replace(/\\s+/g, " ").trim() === t) inner = true;
    });
    if (inner) return;
    el.classList.add("proto-link");
    el.addEventListener("click", function (ev) { ev.stopPropagation(); show(target); });
  });

  show(current);
</script>
'''
(here / "onboarding-prototype.html").write_text(page)
print("wrote onboarding-prototype.html:", len(page), "bytes,", len(frames), "screens")
