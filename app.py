"""Exchange member onboarding portal — Phase 1.

One shared workspace for the member, Operations, Compliance, Service
Management and Technology. Operations is the single channel: KYC vendor
queries and Compliance information requests arrive in the Ops queue and
are routed onward from there.

No authentication in Phase 1 — a persona switcher in the header stands in
for it (see README).
"""

from pathlib import Path

from flask import (Flask, flash, g, redirect, render_template, request,
                   send_from_directory, url_for)

import models as M
from documents import (DECLARATION, DOCS_BY_ID, DOCUMENTS, FORM_SECTIONS,
                       RETURN_TEMPLATES)

UPLOAD_DIR = Path(__file__).parent / "uploads"
MAX_SIZE_MB = 20

app = Flask(__name__)
app.secret_key = "prototype-only"
app.config["MAX_CONTENT_LENGTH"] = MAX_SIZE_MB * 1024 * 1024


@app.before_request
def open_db():
    g.db = M.connect()
    M.init_db(g.db)


@app.teardown_request
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.context_processor
def globals_():
    db = M.connect()
    M.init_db(db)
    counts = {
        "ops": len(ops_queue(db)),
        "compliance": len([a for a in M.all_apps(db) if a["stage"] == "COMPLIANCE"]),
        "tech": len([a for a in M.all_apps(db) if a["stage"] == "PROVISIONING"]),
    }
    db.close()
    return {"STAGE_LABELS": M.STAGE_LABELS, "SLA_DAYS": M.SLA_DAYS,
            "max_size_mb": MAX_SIZE_MB, "nav_counts": counts}


# --------------------------------------------------------------- helpers

def ops_queue(db):
    """Applications needing Operations, longest wait first."""
    rows = []
    for a in M.all_apps(db):
        if a["stage"] in ("LIVE", "REJECTED", "INVITED"):
            continue
        clars = M.app_clarifications(db, a["id"])
        to_route = [c for c in clars if c["status"] == "TO_ROUTE"]
        open_clars = [c for c in clars if c["status"] == "OPEN"]
        docs = M.app_docs(db, a["id"])
        if a["stage"] == "OPS_REVIEW":
            action = ("Send to KYC" if M.ready_to_dispatch(db, a["id"])
                      else "Review pack")
            waiting_on = "Operations"
        elif to_route:
            action, waiting_on = "Route query", "Operations"
        elif a["stage"] == "KYC":
            action, waiting_on = "Open", "KYC vendor"
        elif a["stage"] == "DOCUMENTS":
            action, waiting_on = "Open", "Member"
        else:
            action, waiting_on = "View", M.STAGE_OWNERS[a["stage"]]
        rows.append({
            "app": a, "action": action, "waiting_on": waiting_on,
            "days": M.days_in_stage(db, a["id"]), "day": M.app_day(a),
            "sla": M.sla_state(db, a),
            "to_route": len(to_route), "open_clars": len(open_clars),
            "pending_docs": sum(1 for _, r in docs if r["status"] == "UPLOADED"),
        })
    rows.sort(key=lambda r: (r["waiting_on"] != "Operations", -r["days"]))
    return rows


def member_context(db, app_id):
    a = M.get_app(db, app_id)
    if a is None:
        return None
    docs = M.app_docs(db, app_id)
    clars = M.app_clarifications(db, app_id)
    return {
        "app": a, "docs": docs, "form": M.form_of(a),
        "sections": FORM_SECTIONS, "declaration": DECLARATION,
        "missing": M.form_missing(a),
        "timeline": M.timeline(db, a),
        "clarifications": clars,
        "open_clars": [c for c in clars if c["status"] == "OPEN"],
        "blockers": M.submission_blockers(db, app_id),
        "uploaded": sum(1 for _, r in docs if r["status"] in ("UPLOADED", "ACCEPTED")),
        "accepted": sum(1 for _, r in docs if r["status"] == "ACCEPTED"),
        "total_docs": len(DOCUMENTS),
        "day": M.app_day(a),
        "days_in_stage": M.days_in_stage(db, app_id),
    }


def latest_member(db):
    """The member view defaults to the most recent application."""
    apps = [a for a in M.all_apps(db) if a["stage"] not in ("LIVE", "REJECTED")]
    return (apps or M.all_apps(db))[-1]["id"]


# ---------------------------------------------------------------- routing

@app.route("/")
def home():
    return redirect(url_for("pipeline"))


# --- Service Management -------------------------------------------------

@app.route("/pipeline")
def pipeline():
    rows = []
    for a in M.all_apps(g.db):
        onboarded_in = None
        if a["stage"] == "LIVE":
            live_at = M.stage_entered_at(g.db, a["id"], "LIVE")
            onboarded_in = (live_at - M.parse(a["created_at"])).days
        rows.append({"app": a, "timeline": M.timeline(g.db, a),
                     "days": M.days_in_stage(g.db, a["id"]),
                     "day": M.app_day(a), "sla": M.sla_state(g.db, a),
                     "onboarded_in": onboarded_in})
    rows.sort(key=lambda r: (r["app"]["stage"] in ("LIVE", "REJECTED"), -r["day"]))
    return render_template("pipeline.html", rows=rows,
                           metrics=M.metrics(g.db), persona="service")


@app.route("/new", methods=["GET", "POST"])
def new_application():
    if request.method == "POST":
        f = request.form
        required = ["member_name", "membership_class", "contact_name", "contact_email"]
        if any(not f.get(k, "").strip() for k in required):
            flash("Every field except the sponsor is required.", "error")
            return render_template("new_application.html", form=f,
                                   next_id=M.next_app_id(g.db), persona="service")
        app_id = M.create_application(
            g.db, f["member_name"].strip(), f["membership_class"].strip(),
            f["contact_name"].strip(), f["contact_email"].strip(),
            f.get("sponsor", "").strip() or "A. Lim")
        flash(f"{app_id} created and invitation sent to "
              f"{f['contact_email'].strip()}. The clock starts now.", "ok")
        return redirect(url_for("member_form", app_id=app_id))
    return render_template("new_application.html", form={},
                           next_id=M.next_app_id(g.db), persona="service")


# --- Member -------------------------------------------------------------

@app.route("/m")
def member_home():
    return redirect(url_for("member_status", app_id=latest_member(g.db)))


@app.route("/m/<app_id>")
def member_status(app_id):
    ctx = member_context(g.db, app_id)
    if ctx is None:
        flash("Unknown application.", "error")
        return redirect(url_for("pipeline"))
    if ctx["app"]["stage"] == "LIVE":
        return render_template("member_live.html", persona="member", **ctx)
    if ctx["app"]["stage"] in ("INVITED", "DOCUMENTS") and not ctx["app"]["declared"]:
        return redirect(url_for("member_form", app_id=app_id))
    return render_template("member_status.html", persona="member", **ctx)


@app.route("/m/<app_id>/form", methods=["GET", "POST"])
def member_form(app_id):
    if request.method == "POST":
        M.save_form(g.db, app_id, request.form.to_dict(),
                    request.form.get("declared") == "on")
        if request.form.get("action") == "continue":
            return redirect(url_for("member_documents", app_id=app_id))
        flash("Draft saved.", "ok")
    ctx = member_context(g.db, app_id)
    if ctx is None:
        flash("Unknown application.", "error")
        return redirect(url_for("pipeline"))
    return render_template("member_form.html", persona="member", step=1, **ctx)


@app.route("/m/<app_id>/documents")
def member_documents(app_id):
    ctx = member_context(g.db, app_id)
    if ctx is None:
        flash("Unknown application.", "error")
        return redirect(url_for("pipeline"))
    return render_template("member_documents.html", persona="member", step=2, **ctx)


@app.route("/m/<app_id>/upload/<doc_id>", methods=["POST"])
def upload(app_id, doc_id):
    doc = DOCS_BY_ID.get(doc_id)
    back = request.form.get("back", "documents")
    target = (url_for("member_status", app_id=app_id) if back == "status"
              else url_for("member_documents", app_id=app_id))
    if doc is None:
        flash("Unknown document.", "error")
        return redirect(target)
    file = request.files.get("file")
    if file is None or file.filename == "":
        flash(f"{doc['name']}: no file selected.", "error")
        return redirect(target)
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in doc["formats"]:
        accepted = ", ".join(f".{e}" for e in doc["formats"])
        flash(f"{doc['name']}: .{ext or '?'} is not accepted — expected "
              f"{accepted}.", "error")
        return redirect(target)
    UPLOAD_DIR.mkdir(exist_ok=True)
    stored = f"{app_id}__{doc_id}.{ext}"
    file.save(UPLOAD_DIR / stored)
    M.record_upload(g.db, app_id, doc_id, file.filename)
    flash(f"{doc['name']} received.", "ok")
    return redirect(target)


@app.route("/m/<app_id>/remove/<doc_id>", methods=["POST"])
def remove(app_id, doc_id):
    M.remove_upload(g.db, app_id, doc_id)
    return redirect(url_for("member_documents", app_id=app_id))


@app.route("/m/<app_id>/review")
def member_review(app_id):
    ctx = member_context(g.db, app_id)
    if ctx is None:
        flash("Unknown application.", "error")
        return redirect(url_for("pipeline"))
    return render_template("member_review.html", persona="member", step=3, **ctx)


@app.route("/m/<app_id>/submit", methods=["POST"])
def submit(app_id):
    if M.submit_application(g.db, app_id):
        flash("Application submitted. Operations has it now.", "ok")
        return redirect(url_for("member_status", app_id=app_id))
    flash("Cannot submit yet — see what is outstanding below.", "error")
    return redirect(url_for("member_review", app_id=app_id))


@app.route("/m/<app_id>/answer/<int:clar_id>", methods=["POST"])
def answer(app_id, clar_id):
    text = request.form.get("answer", "").strip()
    if not text:
        flash("Type a reply first.", "error")
    else:
        M.answer_clarification(g.db, clar_id, text)
        flash("Reply sent to Operations.", "ok")
    return redirect(url_for("member_status", app_id=app_id))


# --- Operations ---------------------------------------------------------

@app.route("/ops")
def ops():
    rows = ops_queue(g.db)
    tiles = {
        "waiting": sum(1 for r in rows if r["waiting_on"] == "Operations"),
        "to_review": sum(1 for r in rows if r["action"] == "Review pack"),
        "to_dispatch": sum(1 for r in rows if r["action"] == "Send to KYC"),
        "to_route": sum(r["to_route"] for r in rows),
        "with_vendor": sum(1 for r in rows if r["app"]["stage"] == "KYC"),
        "over_sla": sum(1 for r in rows if r["sla"] == "over"),
        "approaching": sum(1 for r in rows if r["sla"] == "approaching"),
    }
    return render_template("ops_queue.html", rows=rows, tiles=tiles,
                           metrics=M.metrics(g.db), persona="ops")


@app.route("/ops/<app_id>")
def ops_detail(app_id):
    a = M.get_app(g.db, app_id)
    if a is None:
        flash("Unknown application.", "error")
        return redirect(url_for("ops"))
    clars = M.app_clarifications(g.db, app_id)
    return render_template(
        "ops_detail.html", persona="ops", app=a,
        docs=M.app_docs(g.db, app_id), timeline=M.timeline(g.db, a),
        form=M.form_of(a), sections=FORM_SECTIONS, clarifications=clars,
        to_route=[c for c in clars if c["status"] == "TO_ROUTE"],
        open_clars=[c for c in clars if c["status"] == "OPEN"],
        resolved=[c for c in clars if c["status"] == "RESOLVED"],
        ready=M.ready_to_dispatch(g.db, app_id),
        templates=RETURN_TEMPLATES, docs_by_id=DOCS_BY_ID,
        day=M.app_day(a), days_in_stage=M.days_in_stage(g.db, app_id),
        sla=M.sla_state(g.db, a))


@app.route("/ops/<app_id>/accept/<doc_id>", methods=["POST"])
def accept_doc(app_id, doc_id):
    M.accept_doc(g.db, app_id, doc_id)
    if M.ready_to_dispatch(g.db, app_id):
        flash("All documents accepted — the pack is ready to dispatch.", "ok")
    return redirect(url_for("ops_detail", app_id=app_id))


@app.route("/ops/<app_id>/return/<doc_id>", methods=["POST"])
def return_doc(app_id, doc_id):
    reason = (request.form.get("template") or request.form.get("reason", "")).strip()
    if not reason:
        flash("A return needs a reason — that is what saves the round-trip.", "error")
    else:
        M.return_doc(g.db, app_id, doc_id, reason)
        flash(f"{DOCS_BY_ID[doc_id]['name']} returned to the member.", "ok")
    return redirect(url_for("ops_detail", app_id=app_id))


@app.route("/ops/<app_id>/dispatch", methods=["POST"])
def dispatch(app_id):
    if M.dispatch_to_kyc(g.db, app_id):
        flash("Pack dispatched to the KYC vendor on the existing channel, "
              "and recorded here.", "ok")
    else:
        flash("Every document must be accepted before dispatch.", "error")
    return redirect(url_for("ops_detail", app_id=app_id))


@app.route("/ops/<app_id>/vendor-query", methods=["POST"])
def vendor_query(app_id):
    text = request.form.get("text", "").strip()
    if not text:
        flash("Nothing to record.", "error")
    else:
        M.record_vendor_query(g.db, app_id, text)
        flash("Vendor query logged — route it to the member when ready.", "ok")
    return redirect(url_for("ops_detail", app_id=app_id))


@app.route("/ops/route/<int:clar_id>", methods=["POST"])
def route_query(clar_id):
    app_id = request.form["app_id"]
    M.route_to_member(g.db, clar_id, request.form.get("text"))
    flash("Sent to the member as a clarification.", "ok")
    return redirect(url_for("ops_detail", app_id=app_id))


@app.route("/ops/<app_id>/vendor-result", methods=["POST"])
def vendor_result(app_id):
    result = request.form.get("result")
    if result not in ("CLEARED", "FLAGGED"):
        flash("Pick the vendor's outcome.", "error")
        return redirect(url_for("ops_detail", app_id=app_id))
    M.record_vendor_result(g.db, app_id, result,
                           request.form.get("vendor_ref", ""),
                           request.form.get("note", ""))
    flash(f"Vendor result recorded — {app_id} is now with Compliance.", "ok")
    return redirect(url_for("ops_detail", app_id=app_id))


# --- Compliance ---------------------------------------------------------

@app.route("/compliance")
def compliance():
    rows = []
    for a in M.all_apps(g.db):
        if a["stage"] not in ("COMPLIANCE", "REJECTED") and a["decision"] is None:
            continue
        rows.append({"app": a, "days": M.days_in_stage(g.db, a["id"]),
                     "day": M.app_day(a), "sla": M.sla_state(g.db, a)})
    rows.sort(key=lambda r: (r["app"]["stage"] != "COMPLIANCE", -r["days"]))
    return render_template("compliance_queue.html", rows=rows, persona="compliance")


@app.route("/compliance/<app_id>")
def compliance_review(app_id):
    a = M.get_app(g.db, app_id)
    if a is None:
        flash("Unknown application.", "error")
        return redirect(url_for("compliance"))
    clars = M.app_clarifications(g.db, app_id)
    return render_template(
        "compliance_review.html", persona="compliance", app=a,
        docs=M.app_docs(g.db, app_id), timeline=M.timeline(g.db, a),
        form=M.form_of(a), sections=FORM_SECTIONS,
        clarifications=clars, docs_by_id=DOCS_BY_ID,
        day=M.app_day(a), days_in_stage=M.days_in_stage(g.db, app_id))


@app.route("/compliance/<app_id>/decision", methods=["POST"])
def decision(app_id):
    dec = request.form.get("decision")
    rationale = request.form.get("rationale", "").strip()
    if dec not in ("APPROVED", "REJECTED"):
        flash("Choose approve or reject.", "error")
    elif not rationale:
        flash("A decision needs a recorded rationale.", "error")
    else:
        M.record_decision(g.db, app_id, dec, rationale, "C. Menon")
        if dec == "APPROVED":
            flash("Approved — the Technology provisioning task is now open.", "ok")
            return redirect(url_for("tech_detail", app_id=app_id))
        flash("Rejected, with the reason recorded.", "ok")
    return redirect(url_for("compliance_review", app_id=app_id))


@app.route("/compliance/<app_id>/request-info", methods=["POST"])
def request_info(app_id):
    text = request.form.get("text", "").strip()
    if not text:
        flash("Say what you need from the member.", "error")
    else:
        M.record_compliance_request(g.db, app_id, text)
        flash("Sent to the Operations queue — Ops will route it to the member.", "ok")
    return redirect(url_for("compliance_review", app_id=app_id))


# --- Technology ---------------------------------------------------------

@app.route("/tech")
def tech():
    rows = [{"app": a, "tasks": M.app_tasks(g.db, a["id"]),
             "days": M.days_in_stage(g.db, a["id"]), "day": M.app_day(a)}
            for a in M.all_apps(g.db) if a["stage"] in ("PROVISIONING", "LIVE")]
    rows.sort(key=lambda r: (r["app"]["stage"] == "LIVE", -r["days"]))
    return render_template("tech_queue.html", rows=rows, persona="tech")


@app.route("/tech/<app_id>")
def tech_detail(app_id):
    a = M.get_app(g.db, app_id)
    if a is None:
        flash("Unknown application.", "error")
        return redirect(url_for("tech"))
    tasks = M.app_tasks(g.db, app_id)
    return render_template(
        "tech_detail.html", persona="tech", app=a, tasks=tasks,
        timeline=M.timeline(g.db, a), day=M.app_day(a),
        done=sum(1 for t in tasks if t["status"] == "DONE"),
        days_in_stage=M.days_in_stage(g.db, app_id))


@app.route("/tech/<app_id>/task/<int:task_id>", methods=["POST"])
def toggle_task(app_id, task_id):
    M.set_task(g.db, task_id, request.form.get("done") == "on")
    return redirect(url_for("tech_detail", app_id=app_id))


@app.route("/tech/<app_id>/live", methods=["POST"])
def go_live(app_id):
    if M.mark_live(g.db, app_id):
        flash("Member is live. The time-to-onboard clock has stopped.", "ok")
        return redirect(url_for("member_status", app_id=app_id))
    flash("Every provisioning task must be complete first.", "error")
    return redirect(url_for("tech_detail", app_id=app_id))


# --- files --------------------------------------------------------------

@app.route("/file/<app_id>/<doc_id>")
def stored_file(app_id, doc_id):
    doc = DOCS_BY_ID.get(doc_id)
    if doc is None:
        return "Unknown document", 404
    for ext in doc["formats"]:
        if (UPLOAD_DIR / f"{app_id}__{doc_id}.{ext}").exists():
            return send_from_directory(UPLOAD_DIR, f"{app_id}__{doc_id}.{ext}")
    return "Seeded demo document — no file stored on disk.", 404


@app.errorhandler(413)
def too_large(_):
    flash(f"That file is over the {MAX_SIZE_MB} MB limit.", "error")
    return redirect(request.referrer or url_for("pipeline")), 302


if __name__ == "__main__":
    UPLOAD_DIR.mkdir(exist_ok=True)
    if not M.DB_PATH.exists():
        from seed import seed
        seed()
    app.run(debug=True, port=5001)
