"""SQLite storage and the onboarding state machine.

Every stage transition is timestamped in stage_history — the core metric
(time to onboard) and its per-stage breakdown are computed from it, never
stored separately.
"""

import json
import sqlite3
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from documents import DOCUMENTS, FORM_FIELD_IDS

DB_PATH = Path(__file__).parent / "portal.db"

# Ordered pipeline. REJECTED is a terminal side-exit from COMPLIANCE.
STAGES = ["INVITED", "DOCUMENTS", "OPS_REVIEW", "KYC", "COMPLIANCE",
          "PROVISIONING", "LIVE"]
STAGE_LABELS = {
    "INVITED": "Invited", "DOCUMENTS": "Documents",
    "OPS_REVIEW": "Ops review", "KYC": "KYC vendor",
    "COMPLIANCE": "Compliance", "PROVISIONING": "Provisioning",
    "LIVE": "Live", "REJECTED": "Rejected",
}
STAGE_OWNERS = {
    "INVITED": "Service Mgmt", "DOCUMENTS": "Member",
    "OPS_REVIEW": "Operations", "KYC": "Operations · Vendor",
    "COMPLIANCE": "Compliance", "PROVISIONING": "Technology",
    "LIVE": "Done", "REJECTED": "Closed",
}
# Per-stage stall thresholds in days (working assumption #3).
SLA_DAYS = {"DOCUMENTS": 10, "OPS_REVIEW": 3, "KYC": 10,
            "COMPLIANCE": 5, "PROVISIONING": 5}

PROVISIONING_TASKS = [
    "Trading connectivity",
    "Member account & user setup",
    "Market data entitlements",
    "Production readiness check",
]


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS applications (
      id TEXT PRIMARY KEY,
      member_name TEXT NOT NULL,
      membership_class TEXT NOT NULL,
      contact_name TEXT NOT NULL,
      contact_email TEXT NOT NULL,
      sponsor TEXT NOT NULL,
      stage TEXT NOT NULL,
      form_json TEXT NOT NULL DEFAULT '{}',
      declared INTEGER NOT NULL DEFAULT 0,
      kyc_dispatched_at TEXT,
      kyc_result TEXT,
      kyc_vendor_ref TEXT,
      kyc_note TEXT,
      decision TEXT,
      decision_rationale TEXT,
      decided_by TEXT,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS stage_history (
      app_id TEXT NOT NULL REFERENCES applications(id),
      stage TEXT NOT NULL,
      entered_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS documents (
      app_id TEXT NOT NULL REFERENCES applications(id),
      doc_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING',
      filename TEXT,
      return_reason TEXT,
      returns INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT,
      PRIMARY KEY (app_id, doc_id)
    );
    CREATE TABLE IF NOT EXISTS clarifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      app_id TEXT NOT NULL REFERENCES applications(id),
      doc_id TEXT,
      origin TEXT NOT NULL,          -- OPS | VENDOR | COMPLIANCE
      text TEXT NOT NULL,
      status TEXT NOT NULL,          -- TO_ROUTE | OPEN | RESOLVED
      answer TEXT,
      created_at TEXT NOT NULL,
      resolved_at TEXT
    );
    CREATE TABLE IF NOT EXISTS provisioning_tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      app_id TEXT NOT NULL REFERENCES applications(id),
      name TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING'   -- PENDING | DONE
    );
    """)
    db.commit()


def now():
    return datetime.now().isoformat(timespec="seconds")


def parse(ts):
    return datetime.fromisoformat(ts)


# ---------------------------------------------------------------- lifecycle

def next_app_id(db):
    year = datetime.now().year
    row = db.execute("SELECT id FROM applications ORDER BY id DESC LIMIT 1").fetchone()
    seq = int(row["id"].rsplit("-", 1)[1]) + 1 if row else 31
    return f"MEM-{year}-{seq:03d}"


def create_application(db, member_name, membership_class, contact_name,
                       contact_email, sponsor, created_at=None):
    app_id = next_app_id(db)
    ts = created_at or now()
    db.execute(
        "INSERT INTO applications (id, member_name, membership_class, "
        "contact_name, contact_email, sponsor, stage, created_at) "
        "VALUES (?,?,?,?,?,?, 'INVITED', ?)",
        (app_id, member_name, membership_class, contact_name, contact_email,
         sponsor, ts))
    db.execute("INSERT INTO stage_history VALUES (?, 'INVITED', ?)", (app_id, ts))
    for d in DOCUMENTS:
        db.execute("INSERT INTO documents (app_id, doc_id) VALUES (?,?)",
                   (app_id, d["id"]))
    # Pre-fill the form with what Service Mgmt already knows.
    form = {"legal_name": member_name, "membership_class": membership_class,
            "contact_name": contact_name, "contact_email": contact_email}
    db.execute("UPDATE applications SET form_json=? WHERE id=?",
               (json.dumps(form), app_id))
    db.commit()
    return app_id


def set_stage(db, app_id, stage, at=None):
    ts = at or now()
    db.execute("UPDATE applications SET stage=? WHERE id=?", (stage, app_id))
    db.execute("INSERT INTO stage_history VALUES (?,?,?)", (app_id, stage, ts))
    if stage == "PROVISIONING":
        for name in PROVISIONING_TASKS:
            db.execute("INSERT INTO provisioning_tasks (app_id, name) VALUES (?,?)",
                       (app_id, name))
    db.commit()


# ------------------------------------------------------------------- reads

def get_app(db, app_id):
    return db.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()


def all_apps(db):
    return db.execute("SELECT * FROM applications ORDER BY id").fetchall()


def app_docs(db, app_id):
    """The checklist for one application, in DOCUMENTS order.

    Backfills any document added to the checklist after this application was
    created. Without it, adding an entry to DOCUMENTS breaks every existing
    application — the checklist is configuration, so a change to it has to
    reach work already in flight.
    """
    rows = db.execute("SELECT * FROM documents WHERE app_id=?", (app_id,)).fetchall()
    by_id = {r["doc_id"]: r for r in rows}
    missing = [d["id"] for d in DOCUMENTS if d["id"] not in by_id]
    if missing:
        db.executemany("INSERT INTO documents (app_id, doc_id) VALUES (?,?)",
                       [(app_id, doc_id) for doc_id in missing])
        db.commit()
        rows = db.execute("SELECT * FROM documents WHERE app_id=?",
                          (app_id,)).fetchall()
        by_id = {r["doc_id"]: r for r in rows}
    return [(d, by_id[d["id"]]) for d in DOCUMENTS]


def app_clarifications(db, app_id):
    return db.execute(
        "SELECT * FROM clarifications WHERE app_id=? ORDER BY id DESC",
        (app_id,)).fetchall()


def app_tasks(db, app_id):
    return db.execute(
        "SELECT * FROM provisioning_tasks WHERE app_id=? ORDER BY id",
        (app_id,)).fetchall()


def form_of(app):
    return json.loads(app["form_json"])


def form_missing(app):
    form = form_of(app)
    return [fid for fid in FORM_FIELD_IDS
            if fid != "contact_phone" and not form.get(fid, "").strip()]


def stage_entered_at(db, app_id, stage=None):
    """When the app entered its current (or the given) stage, latest entry."""
    if stage is None:
        stage = get_app(db, app_id)["stage"]
    row = db.execute(
        "SELECT entered_at FROM stage_history WHERE app_id=? AND stage=? "
        "ORDER BY entered_at DESC LIMIT 1", (app_id, stage)).fetchone()
    return parse(row["entered_at"]) if row else None


def days_in_stage(db, app_id):
    entered = stage_entered_at(db, app_id)
    return (datetime.now() - entered).days if entered else 0


def app_day(app):
    return (datetime.now() - parse(app["created_at"])).days


def sla_state(db, app):
    """None | 'approaching' | 'over' for the app's current stage."""
    limit = SLA_DAYS.get(app["stage"])
    if limit is None:
        return None
    d = days_in_stage(db, app["id"])
    if d > limit:
        return "over"
    if d >= limit - 1:
        return "approaching"
    return None


def timeline(db, app):
    """The stage strip: list of dicts with state done/current/todo and days."""
    hist = db.execute(
        "SELECT stage, entered_at FROM stage_history WHERE app_id=? "
        "ORDER BY entered_at", (app["id"],)).fetchall()
    entered = {}
    for h in hist:  # latest entry wins (resubmission loops re-enter DOCUMENTS)
        entered[h["stage"]] = parse(h["entered_at"])
    out = []
    current = app["stage"]
    cur_idx = STAGES.index(current) if current in STAGES else len(STAGES)
    for i, s in enumerate(STAGES):
        if s == "INVITED":
            continue
        if s == current:
            state = "current"
            days = (datetime.now() - entered[s]).days if s in entered else 0
        elif i < cur_idx or current == "LIVE":
            state = "done"
            nxt = STAGES[i + 1] if i + 1 < len(STAGES) else None
            days = None
            if s in entered and nxt and nxt in entered:
                days = max((entered[nxt] - entered[s]).days, 0)
        else:
            state = "todo"
            days = None
        out.append({"stage": s, "label": STAGE_LABELS[s],
                    "owner": STAGE_OWNERS[s], "state": state, "days": days})
    if current == "REJECTED":
        out.append({"stage": "REJECTED", "label": "Rejected",
                    "owner": "Closed", "state": "current", "days": None})
    return out


# ------------------------------------------------------------- member flow

def save_form(db, app_id, fields, declared):
    app = get_app(db, app_id)
    form = form_of(app)
    for fid in FORM_FIELD_IDS:
        if fid in fields:
            form[fid] = fields[fid].strip()
    db.execute("UPDATE applications SET form_json=?, declared=? WHERE id=?",
               (json.dumps(form), 1 if declared else 0, app_id))
    if app["stage"] == "INVITED":
        set_stage(db, app_id, "DOCUMENTS")
    db.commit()


def record_upload(db, app_id, doc_id, filename):
    db.execute(
        "UPDATE documents SET status='UPLOADED', filename=?, "
        "return_reason=NULL, updated_at=? WHERE app_id=? AND doc_id=?",
        (filename, now(), app_id, doc_id))
    # A re-upload answers any open clarification tied to this document.
    db.execute(
        "UPDATE clarifications SET status='RESOLVED', resolved_at=?, "
        "answer='Resolved by re-upload' "
        "WHERE app_id=? AND doc_id=? AND status='OPEN'",
        (now(), app_id, doc_id))
    app = get_app(db, app_id)
    if app["stage"] == "INVITED":
        set_stage(db, app_id, "DOCUMENTS")
    db.commit()
    maybe_return_to_ops(db, app_id)


def remove_upload(db, app_id, doc_id):
    db.execute(
        "UPDATE documents SET status='PENDING', filename=NULL, updated_at=? "
        "WHERE app_id=? AND doc_id=? AND status='UPLOADED'",
        (now(), app_id, doc_id))
    db.commit()


def submission_blockers(db, app_id):
    app = get_app(db, app_id)
    blockers = []
    missing = form_missing(app)
    if missing:
        blockers.append(f"{len(missing)} form field(s) still empty")
    if not app["declared"]:
        blockers.append("declaration not signed")
    not_provided = [doc["name"] for doc, row in app_docs(db, app_id)
                    if row["status"] in ("PENDING", "RETURNED")]
    if not_provided:
        blockers.append(f"{len(not_provided)} document(s) outstanding")
    return blockers


def submit_application(db, app_id):
    if submission_blockers(db, app_id):
        return False
    set_stage(db, app_id, "OPS_REVIEW")
    return True


def maybe_return_to_ops(db, app_id):
    """After a fix, an already-submitted application goes back to Ops."""
    app = get_app(db, app_id)
    if app["stage"] != "DOCUMENTS":
        return
    # Was it ever submitted? (Any OPS_REVIEW entry in history.)
    seen = db.execute(
        "SELECT 1 FROM stage_history WHERE app_id=? AND stage='OPS_REVIEW'",
        (app_id,)).fetchone()
    if seen and not submission_blockers(db, app_id):
        set_stage(db, app_id, "OPS_REVIEW")


def answer_clarification(db, clar_id, answer):
    db.execute(
        "UPDATE clarifications SET status='RESOLVED', resolved_at=?, answer=? "
        "WHERE id=? AND status='OPEN'", (now(), answer.strip(), clar_id))
    db.commit()


# ---------------------------------------------------------------- ops flow

def accept_doc(db, app_id, doc_id):
    db.execute(
        "UPDATE documents SET status='ACCEPTED', return_reason=NULL, "
        "updated_at=? WHERE app_id=? AND doc_id=?", (now(), app_id, doc_id))
    db.commit()


def return_doc(db, app_id, doc_id, reason):
    db.execute(
        "UPDATE documents SET status='RETURNED', return_reason=?, "
        "returns=returns+1, updated_at=? WHERE app_id=? AND doc_id=?",
        (reason, now(), app_id, doc_id))
    db.execute(
        "INSERT INTO clarifications (app_id, doc_id, origin, text, status, "
        "created_at) VALUES (?,?,'OPS',?,'OPEN',?)",
        (app_id, doc_id, reason, now()))
    app = get_app(db, app_id)
    if app["stage"] == "OPS_REVIEW":
        set_stage(db, app_id, "DOCUMENTS")
    db.commit()


def ready_to_dispatch(db, app_id):
    return all(row["status"] == "ACCEPTED" for _, row in app_docs(db, app_id))


def dispatch_to_kyc(db, app_id):
    if not ready_to_dispatch(db, app_id):
        return False
    db.execute("UPDATE applications SET kyc_dispatched_at=? WHERE id=?",
               (now(), app_id))
    set_stage(db, app_id, "KYC")
    return True


def record_vendor_query(db, app_id, text):
    db.execute(
        "INSERT INTO clarifications (app_id, origin, text, status, created_at) "
        "VALUES (?,'VENDOR',?,'TO_ROUTE',?)", (app_id, text.strip(), now()))
    db.commit()


def record_compliance_request(db, app_id, text):
    db.execute(
        "INSERT INTO clarifications (app_id, origin, text, status, created_at) "
        "VALUES (?,'COMPLIANCE',?,'TO_ROUTE',?)", (app_id, text.strip(), now()))
    db.commit()


def route_to_member(db, clar_id, text=None):
    """Ops sends a TO_ROUTE query onward; optionally edited first."""
    if text is not None and text.strip():
        db.execute("UPDATE clarifications SET text=? WHERE id=? AND status='TO_ROUTE'",
                   (text.strip(), clar_id))
    db.execute("UPDATE clarifications SET status='OPEN' WHERE id=? AND status='TO_ROUTE'",
               (clar_id,))
    db.commit()


def record_vendor_result(db, app_id, result, vendor_ref, note):
    db.execute(
        "UPDATE applications SET kyc_result=?, kyc_vendor_ref=?, kyc_note=? "
        "WHERE id=?", (result, vendor_ref.strip(), note.strip(), app_id))
    set_stage(db, app_id, "COMPLIANCE")


# --------------------------------------------------- compliance / tech flow

def record_decision(db, app_id, decision, rationale, decided_by):
    db.execute(
        "UPDATE applications SET decision=?, decision_rationale=?, decided_by=? "
        "WHERE id=?", (decision, rationale.strip(), decided_by, app_id))
    set_stage(db, app_id, "PROVISIONING" if decision == "APPROVED" else "REJECTED")


def set_task(db, task_id, done):
    db.execute("UPDATE provisioning_tasks SET status=? WHERE id=?",
               ("DONE" if done else "PENDING", task_id))
    db.commit()


def mark_live(db, app_id):
    tasks = app_tasks(db, app_id)
    if any(t["status"] != "DONE" for t in tasks):
        return False
    set_stage(db, app_id, "LIVE")
    return True


# ---------------------------------------------------------------- metrics

def metrics(db):
    apps = all_apps(db)
    onboard_days = []
    for a in apps:
        if a["stage"] == "LIVE":
            live_at = stage_entered_at(db, a["id"], "LIVE")
            onboard_days.append((live_at - parse(a["created_at"])).days)
    total_docs = accepted_first_time = 0
    for a in apps:
        for _, row in app_docs(db, a["id"]):
            if row["status"] == "ACCEPTED":
                total_docs += 1
                if row["returns"] == 0:
                    accepted_first_time += 1
    in_flight = [a for a in apps if a["stage"] not in ("LIVE", "REJECTED")]
    round_trips = db.execute("SELECT COUNT(*) c FROM clarifications").fetchone()["c"]
    return {
        "median_onboard": round(statistics.median(onboard_days)) if onboard_days else None,
        "first_time_right": round(100 * accepted_first_time / total_docs) if total_docs else None,
        "round_trips_per_app": round(round_trips / len(apps), 1) if apps else 0,
        "in_flight": len(in_flight),
        "live": len(onboard_days),
    }
