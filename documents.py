"""Checklist and form definitions for exchange member onboarding.

The membership application form is filled in the portal (FORM_SECTIONS);
only the supporting documents (DOCUMENTS) are file uploads. One standard
checklist applies to all membership classes (working assumption #1).
"""

DOCUMENTS = [
    {
        "id": "certificate-of-incorporation",
        "name": "Certificate of Incorporation",
        "description": "Proof that the applicant entity is a validly "
                       "incorporated company, issued by ACRA or the "
                       "equivalent registry in your home jurisdiction.",
        "formats": ["pdf"],
    },
    {
        "id": "constitution",
        "name": "Company Constitution",
        "description": "The constitution (or memorandum & articles of "
                       "association) currently in force for the entity.",
        "formats": ["pdf"],
    },
    {
        "id": "board-resolution",
        "name": "Board Resolution",
        "description": "A certified board resolution approving the "
                       "application for exchange membership and authorising the "
                       "named signatories to act for the company.",
        "formats": ["pdf"],
    },
    {
        "id": "shareholding-structure",
        "name": "Shareholding & Group Structure Chart",
        "description": "A chart showing the ownership of the entity up to "
                       "the ultimate beneficial owners, including "
                       "percentage holdings at each level.",
        "formats": ["pdf", "png", "jpg"],
    },
    {
        "id": "audited-financials",
        "name": "Audited Financial Statements",
        "description": "Signed audited financial statements for the last "
                       "two financial years, demonstrating the base "
                       "capital requirement for the membership class.",
        "formats": ["pdf"],
    },
    {
        "id": "directors-officers",
        "name": "Directors & Key Officers List",
        "description": "All directors, CEO and key management, with each "
                       "person's full name, nationality and identification "
                       "(NRIC/passport) number.",
        "formats": ["pdf", "xlsx"],
    },
    {
        "id": "authorised-signatories",
        "name": "Authorised Signatory List",
        "description": "The persons authorised to sign and to communicate "
                       "with the exchange on the member's behalf, with specimen "
                       "signatures.",
        "formats": ["pdf", "xlsx"],
    },
    {
        "id": "regulatory-licence",
        "name": "Regulatory Licence",
        "description": "A copy of your Capital Markets Services licence "
                       "from MAS, or the equivalent licence from your home "
                       "regulator for foreign applicants.",
        "formats": ["pdf"],
    },
    {
        "id": "aml-cft-policy",
        "name": "AML/CFT Policy",
        "description": "Your anti-money-laundering and countering the "
                       "financing of terrorism policy and procedures, as "
                       "currently approved by your board or compliance "
                       "function.",
        "formats": ["pdf", "docx"],
    },
]

DOCS_BY_ID = {d["id"]: d for d in DOCUMENTS}

# The in-portal membership application form, section by section.
FORM_SECTIONS = [
    {
        "id": "company",
        "name": "Company details",
        "fields": [
            {"id": "legal_name", "label": "Legal entity name", "placeholder": "e.g. Meridian Trading Pte Ltd"},
            {"id": "uen", "label": "UEN / registration number", "placeholder": "e.g. 202412345K"},
            {"id": "country", "label": "Country of incorporation", "placeholder": "e.g. Singapore"},
            {"id": "incorporated_on", "label": "Date of incorporation", "placeholder": "e.g. 14 Mar 2024"},
            {"id": "address", "label": "Registered address", "placeholder": "e.g. 12 Marina Boulevard, #21-01, Singapore 018982", "wide": True},
        ],
    },
    {
        "id": "membership",
        "name": "Membership applied for",
        "fields": [
            {"id": "membership_class", "label": "Membership class", "placeholder": "e.g. Securities trading member"},
            {"id": "regulator", "label": "Regulated by", "placeholder": "e.g. MAS — Capital Markets Services licence"},
            {"id": "licence_no", "label": "Licence number", "placeholder": "e.g. CMS100482", "wide": True},
        ],
    },
    {
        "id": "contact",
        "name": "Primary contact for this application",
        "fields": [
            {"id": "contact_name", "label": "Full name", "placeholder": "e.g. Tan Wei Ling"},
            {"id": "contact_email", "label": "Email", "placeholder": "e.g. weiling.tan@meridian.sg"},
            {"id": "contact_phone", "label": "Phone", "placeholder": "e.g. +65 6123 4567"},
        ],
    },
]

FORM_FIELD_IDS = [f["id"] for s in FORM_SECTIONS for f in s["fields"]]

DECLARATION = ("I declare that the information provided in this application "
               "is true and complete, and that I am authorised to submit it "
               "on behalf of the applicant entity.")

# Common return reasons offered to Ops as one-click templates (PRD 5.3).
RETURN_TEMPLATES = [
    "The financial statements are unsigned — please upload the signed audited version.",
    "The structure chart does not show percentages at every level — please upload an updated chart.",
    "The licence copy has expired or is the application letter — please upload the current licence.",
    "The document is illegible — please upload a clearer copy.",
]
