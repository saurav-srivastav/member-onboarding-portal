"""Build the print-deck HTML for the mock-ups PDF and the prototype-walkthrough
PDF (with the app-shell sidebar) from the mockups/*.dc.html sources.

Render afterwards with headless Chrome:
  chrome --headless --no-pdf-header-footer --print-to-pdf=out.pdf file://.../deck.html
"""

import re
import pathlib

here = pathlib.Path(__file__).parent.parent / "mockups"
out = pathlib.Path(__file__).parent

FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">'

BASE_CSS = '''
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { margin: 0; font-family: "IBM Plex Sans", -apple-system, sans-serif; color: #1a2332; }
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
'''


def body_of(f):
    src = (here / f).read_text()
    b = re.search(r"<x-dc>(.*)</x-dc>", src, re.S).group(1)
    return re.sub(r"<helmet>.*?</helmet>", "", b, flags=re.S).strip()


# ---------------------------------------------------------------- mock-ups deck

MOCK = [
    ("ApplicationForm.dc.html", "Member — application form", "Day 1 · the membership application is a structured in-portal form, not a PDF upload"),
    ("DocumentUpload.dc.html", "Member — supporting documents", "Day 1 · formats validated at upload; common return reasons shown before submission"),
    ("Main.dc.html", "Member — status after submission", "Day 6 · per-document status, live stage timeline, clarifications in one place"),
    ("OpsQueue.dc.html", "Operations — queue", "Applications ordered by time waiting on Ops; SLA breaches surfaced"),
    ("ApplicationDetail.dc.html", "Operations — application detail", "The pack plus the clarification hub; vendor and Compliance queries route via Ops"),
    ("ComplianceReview.dc.html", "Compliance — review & decision", "KYC result, pack, query history and a recorded decision on one page"),
    ("Pipeline.dc.html", "Service Management — pipeline", "Every in-flight application against the stages; core metrics on top"),
]

MOCK_CSS = BASE_CSS + '''
  @page { size: 15in 10.15in; margin: 0; }
  .pg { width: 1440px; height: 974.4px; page-break-after: always; background: #e9e7e2; overflow: hidden; }
  .pg:last-child { page-break-after: auto; }
  .cap { height: 74.4px; display: flex; align-items: center; gap: 14px; padding: 0 36px; box-sizing: border-box; }
  .cap .n { font-family: "IBM Plex Mono", monospace; font-size: 13px; color: #c0392f; }
  .cap b { font-family: "Schibsted Grotesk", sans-serif; font-size: 17px; font-weight: 700; }
  .cap span { font-size: 12.5px; color: #5a6473; }
  .cover { display: flex; flex-direction: column; justify-content: center; padding: 0 110px; box-sizing: border-box; }
'''

MOCK_COVER = '''
  <div class="mono" style="font-size: 13px; letter-spacing: 0.14em; text-transform: uppercase; color: #c0392f; margin-bottom: 16px;">Screen mock-ups · accompanies the PRD</div>
  <div class="h" style="font-size: 46px; font-weight: 700; letter-spacing: -0.015em; margin-bottom: 14px;">Exchange Member Onboarding Portal</div>
  <div style="font-size: 18px; color: #5a6473; max-width: 62ch; line-height: 1.6; margin-bottom: 26px;">Seven key screens across the four personas, sharing a single design system. Screens 1–3 follow one member (Meridian Trading) through time — filling on day 1, tracking status on day 6 — while the internal screens show the same moment from inside the exchange, with every sample application's status consistent across views.</div>
  <div style="background: #f7f2ea; border: 1px solid #e4dcc9; border-radius: 8px; padding: 16px 22px; font-size: 15px; color: #6e5417; max-width: 72ch; line-height: 1.6;"><b>Interaction rule carried through every screen:</b> the KYC vendor talks only to Operations, and Compliance reaches the member only through Operations. Vendor and Compliance queries land in the Ops queue as route-onward items, so the member always hears a single voice — with every hop timestamped for the time-to-onboard metric.</div>
'''


def build_mock_deck():
    parts = [f'<meta charset="utf-8"><title>Member Onboarding Portal — Screen Designs</title>'
             f'{FONT}<style>{MOCK_CSS}</style>']
    parts.append(f'<div class="pg cover">{MOCK_COVER}</div>')
    for i, (f, title, sub) in enumerate(MOCK, 1):
        parts.append(
            f'<div class="pg"><div class="cap"><span class="n">{i:02d}</span><b>{title}</b>'
            f'<span>{sub}</span></div>{body_of(f)}</div>')
    (out / "mockups-deck.html").write_text("\n".join(parts))
    print("wrote mockups-deck.html")


# ------------------------------------------------- prototype walkthrough deck

PROTO = [
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

PROTO_CSS = BASE_CSS + '''
  @page { size: 17.61in 9.86in; margin: 0; }
  .pg { width: 1690px; height: 946px; page-break-after: always; background: #e9e7e2;
        overflow: hidden; display: flex; }
  .pg:last-child { page-break-after: auto; }
  .side { width: 250px; flex-shrink: 0; background: #1a2332; color: #ffffff;
          display: flex; flex-direction: column; padding: 20px 0 14px; box-sizing: border-box; }
  .side .brand { padding: 0 20px 14px; border-bottom: 1px solid #2b3444; }
  .side .brand .t { font-family: "Schibsted Grotesk", sans-serif; font-weight: 700; font-size: 15px; }
  .side .brand .s { font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: 0.12em;
                    text-transform: uppercase; color: #8b95a5; margin-top: 3px; }
  .grouplabel { font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: 0.12em;
                text-transform: uppercase; color: #6c7686; padding: 16px 20px 6px; }
  .navitem { display: flex; gap: 10px; align-items: flex-start; padding: 8px 20px; }
  .navitem.active { background: #2b3444; box-shadow: inset 3px 0 0 #e0685c; }
  .navitem .n { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: #e0685c; padding-top: 2px; width: 14px; }
  .navitem b { display: block; font-size: 13px; font-weight: 600; }
  .navitem i { display: block; font-style: normal; font-size: 11px; color: #8b95a5; margin-top: 1px; }
  .side .hint { margin-top: auto; padding: 14px 20px 0; font-size: 11.5px; color: #8b95a5; line-height: 1.5;
                border-top: 1px solid #2b3444; }
  .main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .topbar { height: 46px; display: flex; align-items: center; padding: 0 22px; box-sizing: border-box;
            font-size: 13.5px; color: #5a6473; }
  .topbar b { color: #1a2332; font-weight: 600; }
  .screenbox { width: 1440px; height: 900px; }
  .cover { flex-direction: column; justify-content: center; padding: 0 110px; box-sizing: border-box; }
'''

PROTO_COVER = '''
  <div class="mono" style="font-size: 13px; letter-spacing: 0.14em; text-transform: uppercase; color: #c0392f; margin-bottom: 16px;">Prototype walkthrough · print version</div>
  <div class="h" style="font-size: 46px; font-weight: 700; letter-spacing: -0.015em; margin-bottom: 14px;">Exchange Member Onboarding Portal</div>
  <div style="font-size: 18px; color: #5a6473; max-width: 64ch; line-height: 1.6; margin-bottom: 26px;">Eleven screens covering the full flow, in walkthrough order: the member journey from invitation to submission (1–5), then the same applications seen from inside the exchange — Operations, Compliance, Technology and Service Management (6–11). Each page reproduces the prototype view, with the navigation pane showing where you are. The interactive version is clickable; this document is its print rendering.</div>
  <div style="font-size: 15px; color: #37404f; max-width: 64ch; line-height: 1.9;">
    <b class="h" style="font-size: 16px;">The flow</b><br>
    Create &amp; invite → Application form → Supporting documents → Review &amp; submit → Status &amp; clarifications<br>
    Queue → Application detail → Review &amp; decision → Provisioning → Live on the exchange → Pipeline &amp; metrics
  </div>
'''


def sidebar(active):
    rows_m, rows_i = [], []
    for i, (sid, _, label, sub) in enumerate(PROTO, 1):
        cls = "navitem active" if sid == active else "navitem"
        row = (f'<div class="{cls}"><span class="n">{i}</span>'
               f'<span><b>{label}</b><i>{sub}</i></span></div>')
        (rows_m if sid in MEMBER_IDS else rows_i).append(row)
    return ('<div class="side"><div class="brand"><div class="t">Exchange · Member Onboarding</div>'
            '<div class="s">Clickable prototype · v1</div></div>'
            '<div class="grouplabel">Member journey</div>' + "".join(rows_m) +
            '<div class="grouplabel">Inside the exchange</div>' + "".join(rows_i) +
            '<div class="hint">Print rendering of the clickable prototype — in the live version, '
            'highlighted elements navigate the flow.</div></div>')


def build_proto_deck():
    parts = [f'<meta charset="utf-8"><title>Member Onboarding Portal — Prototype Walkthrough</title>'
             f'{FONT}<style>{PROTO_CSS}</style>']
    parts.append(f'<div class="pg cover">{PROTO_COVER}</div>')
    for i, (sid, f, label, sub) in enumerate(PROTO, 1):
        parts.append(
            f'<div class="pg">{sidebar(sid)}'
            f'<div class="main"><div class="topbar"><b>{i} / {len(PROTO)}</b>&nbsp; {label} — {sub}</div>'
            f'<div class="screenbox">{body_of(f)}</div></div></div>')
    (out / "prototype-deck.html").write_text("\n".join(parts))
    print("wrote prototype-deck.html")


if __name__ == "__main__":
    build_mock_deck()
    build_proto_deck()
