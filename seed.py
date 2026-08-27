"""Seed the portal with the demo applications used in the mock-ups.

Dates are relative to today, so the demo always reads the same way:
Meridian on day 6 with one returned document, Pacific Rim over SLA in Ops
review, Nikko waiting on the vendor with a query to route, Lion City in
compliance, plus three onboarded members so the metrics have history.
"""

import json
from datetime import datetime, timedelta

from documents import DOCUMENTS
from models import DB_PATH, PROVISIONING_TASKS, connect, init_db


def ago(days):
    return (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")


def add(db, app_id, member, klass, contact, email, sponsor, day, history,
        doc_status, form=None, returned_once=(), **extra):
    """history: list of (stage, days_ago). doc_status: dict or 'all-accepted'.

    returned_once: doc ids that were returned before being accepted — they
    count against first-time-right without being outstanding now.
    """
    db.execute(
        "INSERT INTO applications (id, member_name, membership_class, "
        "contact_name, contact_email, sponsor, stage, form_json, declared, "
        "kyc_dispatched_at, kyc_result, kyc_vendor_ref, kyc_note, decision, "
        "decision_rationale, decided_by, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?)",
        (app_id, member, klass, contact, email, sponsor, history[-1][0],
         json.dumps(form or {}), extra.get("kyc_dispatched_at"),
         extra.get("kyc_result"), extra.get("kyc_vendor_ref"),
         extra.get("kyc_note"), extra.get("decision"),
         extra.get("decision_rationale"), extra.get("decided_by"), ago(day)))
    for stage, d in history:
        db.execute("INSERT INTO stage_history VALUES (?,?,?)", (app_id, stage, ago(d)))
    for d in DOCUMENTS:
        if doc_status == "all-accepted":
            status, reason, returns = "ACCEPTED", None, 0
        elif isinstance(doc_status, dict):
            entry = doc_status.get(d["id"], doc_status.get("*", "PENDING"))
            if isinstance(entry, tuple):
                status, reason, returns = entry
            else:
                status, reason, returns = entry, None, 0
        else:
            status, reason, returns = doc_status, None, 0
        if d["id"] in returned_once:
            returns = max(returns, 1)
        fname = None
        if status in ("UPLOADED", "ACCEPTED"):
            fname = d["id"].replace("-", "_") + "." + d["formats"][0]
        db.execute(
            "INSERT INTO documents (app_id, doc_id, status, filename, "
            "return_reason, returns, updated_at) VALUES (?,?,?,?,?,?,?)",
            (app_id, d["id"], status, fname, reason, returns, ago(day - 1)))


def clarification(db, app_id, origin, text, status, doc_id=None, days=1,
                  answer=None):
    db.execute(
        "INSERT INTO clarifications (app_id, doc_id, origin, text, status, "
        "answer, created_at, resolved_at) VALUES (?,?,?,?,?,?,?,?)",
        (app_id, doc_id, origin, text, status, answer, ago(days),
         ago(days - 1) if status == "RESOLVED" else None))


def tasks(db, app_id, done_count):
    for i, name in enumerate(PROVISIONING_TASKS):
        db.execute("INSERT INTO provisioning_tasks (app_id, name, status) "
                   "VALUES (?,?,?)", (app_id, name, "DONE" if i < done_count else "PENDING"))


def seed():
    if DB_PATH.exists():
        DB_PATH.unlink()
    db = connect()
    init_db(db)

    # --- onboarded members, for the metrics history ---------------------
    for app_id, member, klass, total, sponsor, returned in [
        ("MEM-2026-031", "Kallang Capital Markets", "Securities trading member",
         35, "A. Lim", ("audited-financials", "shareholding-structure", "aml-cft-policy")),
        ("MEM-2026-033", "Anson Futures Pte Ltd", "Derivatives trading member",
         32, "R. Devi", ("directors-officers", "regulatory-licence")),
        ("MEM-2026-035", "Tanjong Clearing Services", "Clearing member",
         28, "A. Lim", ("audited-financials",)),
    ]:
        add(db, app_id, member, klass, "Operations contact",
            "ops@example.sg", sponsor, total + 4,
            [("INVITED", total + 4), ("DOCUMENTS", total + 3),
             ("OPS_REVIEW", total - 8), ("KYC", total - 12),
             ("COMPLIANCE", total - 18), ("PROVISIONING", total - 22),
             ("LIVE", 4)],
            "all-accepted", returned_once=returned,
            kyc_result="CLEARED", kyc_vendor_ref="KV-0000",
            kyc_note="No adverse findings.", decision="APPROVED",
            decision_rationale="KYC cleared; capital requirement met.",
            decided_by="C. Menon")
        tasks(db, app_id, 4)
        for doc_id in returned:
            clarification(db, app_id, "OPS",
                          "Returned during Ops review — resolved before dispatch.",
                          "RESOLVED", doc_id=doc_id, days=total - 6)
        clarification(db, app_id, "VENDOR",
                      "Vendor query during screening — answered via Ops.",
                      "RESOLVED", days=total - 14)

    # --- Lion City Brokerage: in compliance, KYC cleared -----------------
    add(db, "MEM-2026-034", "Lion City Brokerage", "Securities trading member",
        "Ravi Kumar", "ravi.kumar@lioncity.sg", "R. Devi", 26,
        [("INVITED", 26), ("DOCUMENTS", 25), ("OPS_REVIEW", 13),
         ("KYC", 9), ("COMPLIANCE", 3)],
        "all-accepted",
        form={"legal_name": "Lion City Brokerage", "uen": "201998765C",
              "country": "Singapore", "incorporated_on": "8 Jan 2020",
              "address": "80 Robinson Road, #14-02, Singapore 068898",
              "membership_class": "Securities trading member",
              "regulator": "MAS — Capital Markets Services licence",
              "licence_no": "CMS100221", "contact_name": "Ravi Kumar",
              "contact_email": "ravi.kumar@lioncity.sg",
              "contact_phone": "+65 6222 8100"},
        returned_once=("audited-financials",),
        kyc_dispatched_at=ago(9), kyc_result="CLEARED",
        kyc_vendor_ref="KV-88213",
        kyc_note="No adverse media or sanctions matches. Beneficial ownership "
                 "verified against updated structure chart received 22 Aug.")
    clarification(db, "MEM-2026-034", "OPS",
                  "The FY2024 statement is unsigned — please upload the signed "
                  "audited version.", "RESOLVED",
                  doc_id="audited-financials", days=16,
                  answer="Resolved by re-upload")
    clarification(db, "MEM-2026-034", "VENDOR",
                  "Beneficial owner listed at 22% does not appear in the registry "
                  "extract. Please confirm current shareholding.", "RESOLVED",
                  days=6, answer="Updated structure chart provided.")

    # --- Nikko Futures: with the vendor, query waiting for Ops to route --
    add(db, "MEM-2026-036", "Nikko Futures SG", "Derivatives trading member",
        "Aiko Tanaka", "aiko.tanaka@nikkofutures.sg", "A. Lim", 23,
        [("INVITED", 23), ("DOCUMENTS", 22), ("OPS_REVIEW", 11), ("KYC", 7)],
        "all-accepted",
        form={"legal_name": "Nikko Futures SG", "uen": "202211223D",
              "country": "Singapore", "incorporated_on": "3 May 2022",
              "address": "9 Raffles Place, #26-01, Singapore 048619",
              "membership_class": "Derivatives trading member",
              "regulator": "MAS — Capital Markets Services licence",
              "licence_no": "CMS100774", "contact_name": "Aiko Tanaka",
              "contact_email": "aiko.tanaka@nikkofutures.sg",
              "contact_phone": "+65 6533 2210"},
        returned_once=("audited-financials",), kyc_dispatched_at=ago(7))
    clarification(db, "MEM-2026-036", "VENDOR",
                  "Beneficial owner listed at 22% in the structure chart does not "
                  "appear in the registry extract. Please confirm current "
                  "shareholding or provide an updated chart.", "TO_ROUTE", days=0)
    clarification(db, "MEM-2026-036", "OPS",
                  "FY2024 statement unsigned — please upload the signed audited "
                  "version.", "RESOLVED", doc_id="audited-financials", days=13,
                  answer="Resolved by re-upload")

    # --- Pacific Rim: sitting in Ops review, over SLA --------------------
    add(db, "MEM-2026-037", "Pacific Rim Securities", "Securities trading member",
        "Grace Ho", "grace.ho@pacificrim.sg", "R. Devi", 21,
        [("INVITED", 21), ("DOCUMENTS", 20), ("OPS_REVIEW", 9)],
        "UPLOADED",
        form={"legal_name": "Pacific Rim Securities", "uen": "202033445E",
              "country": "Singapore", "incorporated_on": "17 Sep 2020",
              "address": "1 Raffles Quay, #30-05, Singapore 048583",
              "membership_class": "Securities trading member",
              "regulator": "MAS — Capital Markets Services licence",
              "licence_no": "CMS100655", "contact_name": "Grace Ho",
              "contact_email": "grace.ho@pacificrim.sg",
              "contact_phone": "+65 6788 1200"})

    # --- Straits Derivatives: all accepted, ready to dispatch ------------
    add(db, "MEM-2026-039", "Straits Derivatives", "Derivatives trading member",
        "Marcus Yeo", "marcus.yeo@straitsderiv.sg", "A. Lim", 12,
        [("INVITED", 12), ("DOCUMENTS", 11), ("OPS_REVIEW", 1)],
        "all-accepted",
        form={"legal_name": "Straits Derivatives", "uen": "202144556F",
              "country": "Singapore", "incorporated_on": "2 Feb 2021",
              "address": "12 Marina View, #18-01, Singapore 018961",
              "membership_class": "Derivatives trading member",
              "regulator": "MAS — Capital Markets Services licence",
              "licence_no": "CMS100901", "contact_name": "Marcus Yeo",
              "contact_email": "marcus.yeo@straitsderiv.sg",
              "contact_phone": "+65 6900 3311"})

    # --- Harbourfront Capital: in Ops review, checklist complete ---------
    add(db, "MEM-2026-040", "Harbourfront Capital", "Securities trading member",
        "Nadia Rahman", "nadia.rahman@harbourfront.sg", "R. Devi", 9,
        [("INVITED", 9), ("DOCUMENTS", 8), ("OPS_REVIEW", 2)],
        "UPLOADED",
        form={"legal_name": "Harbourfront Capital", "uen": "202255667G",
              "country": "Singapore", "incorporated_on": "21 Jun 2022",
              "address": "3 HarbourFront Place, #09-02, Singapore 099254",
              "membership_class": "Securities trading member",
              "regulator": "MAS — Capital Markets Services licence",
              "licence_no": "CMS101044", "contact_name": "Nadia Rahman",
              "contact_email": "nadia.rahman@harbourfront.sg",
              "contact_phone": "+65 6377 4400"})

    # --- Meridian Trading: the member walkthrough, one doc returned ------
    add(db, "MEM-2026-041", "Meridian Trading Pte Ltd", "Securities trading member",
        "Tan Wei Ling", "weiling.tan@meridian.sg", "A. Lim", 6,
        [("INVITED", 6), ("DOCUMENTS", 5), ("OPS_REVIEW", 2), ("DOCUMENTS", 1)],
        {"*": "ACCEPTED",
         "audited-financials": ("RETURNED",
                                "The FY2024 statement is unsigned — please "
                                "upload the signed audited version.", 1)},
        form={"legal_name": "Meridian Trading Pte Ltd", "uen": "202412345K",
              "country": "Singapore", "incorporated_on": "14 Mar 2024",
              "address": "12 Marina Boulevard, #21-01, Singapore 018982",
              "membership_class": "Securities trading member",
              "regulator": "MAS — Capital Markets Services licence",
              "licence_no": "CMS100482", "contact_name": "Tan Wei Ling",
              "contact_email": "weiling.tan@meridian.sg",
              "contact_phone": "+65 6812 4400"})
    clarification(db, "MEM-2026-041", "OPS",
                  "The FY2024 statement is unsigned — please upload the signed "
                  "audited version.", "OPEN", doc_id="audited-financials", days=1)

    db.commit()
    counts = db.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"]
    print(f"seeded {counts} applications into {DB_PATH.name}")


if __name__ == "__main__":
    seed()
