"""End-to-end test: one member from invitation to live, through every actor.

Runs against a temporary database so it never touches the demo data.
"""

import io
import os
import tempfile

# Point the app at a scratch database before anything imports models.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
import models as M  # noqa: E402
M.DB_PATH = __import__("pathlib").Path(_tmp.name)

import app as A  # noqa: E402
from documents import DOCUMENTS  # noqa: E402

A.UPLOAD_DIR = __import__("pathlib").Path(tempfile.mkdtemp())
client = A.app.test_client()

checks = 0


def ok(label, cond):
    global checks
    checks += 1
    assert cond, f"FAILED: {label}"
    print(f"  ok  {label}")


def text(resp):
    return resp.get_data(as_text=True)


def upload(app_id, doc_id, filename, follow=True):
    return client.post(f"/m/{app_id}/upload/{doc_id}", follow_redirects=follow,
                       data={"file": (io.BytesIO(b"%PDF-1.4 x"), filename)})


def db():
    d = M.connect()
    M.init_db(d)
    return d


print("\n1 · Service Management creates the application")
r = client.post("/new", follow_redirects=True, data={
    "member_name": "Testbed Securities Pte Ltd",
    "membership_class": "Securities trading member",
    "contact_name": "Alex Tan", "contact_email": "alex@testbed.sg",
    "sponsor": "A. Lim"})
d = db()
app_id = M.all_apps(d)[0]["id"]
ok("application created in INVITED", M.get_app(d, app_id)["stage"] == "INVITED")
ok("all 9 documents are on the checklist", len(M.app_docs(d, app_id)) == len(DOCUMENTS) == 9)
ok("redirected to the member form", "Membership application form" in text(r))

print("\n2 · Member fills the in-portal form")
form = {"legal_name": "Testbed Securities Pte Ltd", "uen": "202400001A",
        "country": "Singapore", "incorporated_on": "1 Jan 2024",
        "address": "1 Test Way, Singapore 000001",
        "membership_class": "Securities trading member",
        "regulator": "MAS", "licence_no": "CMS100000",
        "contact_name": "Alex Tan", "contact_email": "alex@testbed.sg",
        "declared": "on", "action": "continue"}
client.post(f"/m/{app_id}/form", data=form, follow_redirects=True)
d = db()
ok("form saved and stage moved to DOCUMENTS", M.get_app(d, app_id)["stage"] == "DOCUMENTS")
ok("no form fields outstanding", M.form_missing(M.get_app(d, app_id)) == [])

print("\n3 · Uploads are validated at the point of upload")
r = upload(app_id, "certificate-of-incorporation", "cert.txt")
ok("wrong format is rejected, naming the expected format",
   "not accepted" in text(r) and ".pdf" in text(r))
d = db()
ok("nothing was stored for the rejected file",
   all(row["status"] == "PENDING" for _, row in M.app_docs(d, app_id)))

r = client.post(f"/m/{app_id}/submit", follow_redirects=True)
ok("submission is blocked while documents are outstanding",
   "Cannot submit yet" in text(r))
d = db()
ok("stage did not move on the blocked submit", M.get_app(d, app_id)["stage"] == "DOCUMENTS")

for doc in DOCUMENTS:
    upload(app_id, doc["id"], f"{doc['id']}.{doc['formats'][0]}")
d = db()
ok("all 9 documents uploaded",
   sum(1 for _, r_ in M.app_docs(d, app_id) if r_["status"] == "UPLOADED") == 9)
ok("no blockers remain", M.submission_blockers(d, app_id) == [])

print("\n4 · Member submits — the hand-off to Operations")
client.post(f"/m/{app_id}/submit", follow_redirects=True)
d = db()
ok("stage is OPS_REVIEW", M.get_app(d, app_id)["stage"] == "OPS_REVIEW")

print("\n5 · Ops returns one document with a reason")
reason = "The FY2024 statement is unsigned — please upload the signed audited version."
client.post(f"/ops/{app_id}/return/audited-financials",
            data={"template": reason}, follow_redirects=True)
d = db()
docs = dict((doc["id"], row) for doc, row in M.app_docs(d, app_id))
ok("only that document is RETURNED", docs["audited-financials"]["status"] == "RETURNED")
ok("the other documents keep their status",
   sum(1 for r_ in docs.values() if r_["status"] == "UPLOADED") == 8)
ok("the application went back to the member", M.get_app(d, app_id)["stage"] == "DOCUMENTS")
clars = M.app_clarifications(d, app_id)
ok("a clarification was raised with the reason",
   len(clars) == 1 and clars[0]["origin"] == "OPS" and clars[0]["status"] == "OPEN")

print("\n6 · Member re-uploads — the loop closes without a new submission")
upload(app_id, "audited-financials", "fy2024-signed.pdf")
d = db()
ok("document is uploaded again",
   dict((doc["id"], r_) for doc, r_ in M.app_docs(d, app_id))["audited-financials"]["status"] == "UPLOADED")
ok("re-upload resolved the clarification",
   M.app_clarifications(d, app_id)[0]["status"] == "RESOLVED")
ok("application returned to Ops automatically",
   M.get_app(d, app_id)["stage"] == "OPS_REVIEW")

print("\n7 · Ops accepts everything and dispatches to the KYC vendor")
d = db()
ok("dispatch is refused while documents are unreviewed",
   not M.ready_to_dispatch(d, app_id))
for doc in DOCUMENTS:
    client.post(f"/ops/{app_id}/accept/{doc['id']}", follow_redirects=True)
d = db()
ok("all documents accepted", M.ready_to_dispatch(d, app_id))
client.post(f"/ops/{app_id}/dispatch", follow_redirects=True)
d = db()
ok("stage is KYC", M.get_app(d, app_id)["stage"] == "KYC")
ok("dispatch is timestamped", M.get_app(d, app_id)["kyc_dispatched_at"] is not None)

print("\n8 · A vendor query reaches the member only through Ops")
client.post(f"/ops/{app_id}/vendor-query",
            data={"text": "Confirm the 22% beneficial owner."}, follow_redirects=True)
d = db()
vendor = [c for c in M.app_clarifications(d, app_id) if c["origin"] == "VENDOR"][0]
ok("vendor query waits in the Ops queue, not with the member",
   vendor["status"] == "TO_ROUTE")
r = client.get(f"/m/{app_id}")
ok("member cannot see it before Ops routes it",
   "22% beneficial owner" not in text(r))
client.post(f"/ops/route/{vendor['id']}", data={"app_id": app_id}, follow_redirects=True)
r = client.get(f"/m/{app_id}")
ok("after routing, the member sees it", "22% beneficial owner" in text(r))
client.post(f"/m/{app_id}/answer/{vendor['id']}",
            data={"answer": "Shareholding confirmed at 22%."}, follow_redirects=True)
d = db()
ok("the member's reply resolves it",
   [c for c in M.app_clarifications(d, app_id) if c["id"] == vendor["id"]][0]["status"] == "RESOLVED")

print("\n9 · Ops records the vendor result; Compliance decides")
client.post(f"/ops/{app_id}/vendor-result",
            data={"result": "CLEARED", "vendor_ref": "KV-00001",
                  "note": "No adverse findings."}, follow_redirects=True)
d = db()
ok("stage is COMPLIANCE", M.get_app(d, app_id)["stage"] == "COMPLIANCE")
ok("vendor result is recorded", M.get_app(d, app_id)["kyc_result"] == "CLEARED")

r = client.post(f"/compliance/{app_id}/request-info",
                data={"text": "Confirm the settlement bank."}, follow_redirects=True)
d = db()
comp = [c for c in M.app_clarifications(d, app_id) if c["origin"] == "COMPLIANCE"][0]
ok("a compliance request also routes through Ops", comp["status"] == "TO_ROUTE")

r = client.post(f"/compliance/{app_id}/decision",
                data={"decision": "APPROVED", "rationale": ""}, follow_redirects=True)
ok("a decision without rationale is refused", "needs a recorded rationale" in text(r))
d = db()
ok("stage unchanged after the refused decision",
   M.get_app(d, app_id)["stage"] == "COMPLIANCE")

client.post(f"/compliance/{app_id}/decision",
            data={"decision": "APPROVED",
                  "rationale": "KYC cleared; capital requirement met."},
            follow_redirects=True)
d = db()
ok("approval opens provisioning", M.get_app(d, app_id)["stage"] == "PROVISIONING")
ok("the provisioning checklist was created automatically",
   len(M.app_tasks(d, app_id)) == len(M.PROVISIONING_TASKS))

print("\n10 · Technology provisions, then the member goes live")
r = client.post(f"/tech/{app_id}/live", follow_redirects=True)
ok("go-live is refused while tasks are open", "must be complete first" in text(r))
d = db()
for t in M.app_tasks(d, app_id):
    client.post(f"/tech/{app_id}/task/{t['id']}", data={"done": "on"},
                follow_redirects=True)
client.post(f"/tech/{app_id}/live", follow_redirects=True)
d = db()
ok("stage is LIVE", M.get_app(d, app_id)["stage"] == "LIVE")

print("\n11 · The metric falls out of the stage history")
d = db()
tl = M.timeline(d, M.get_app(d, app_id))
ok("every stage on the timeline is complete",
   all(s["state"] == "done" for s in tl[:-1]))
mets = M.metrics(d)
ok("time to onboard is computed", mets["median_onboard"] is not None)
ok("first-time-right counts the returned document",
   mets["first_time_right"] == round(100 * 8 / 9))
r = client.get(f"/m/{app_id}")
ok("member sees the live page", "You're live on the exchange" in text(r))

os.unlink(_tmp.name)
print(f"\ntest_app: {checks} checks passed")
