HALQA: SUBMISSION SUMMARY
Challenge 05, Closing the Screening-to-Care Loop. Team Latitude-IT.

PROBLEM
A raised blood pressure found at screening often does not become care. The result is issued, but nobody owns the next step, patients may not understand it, referrals stall between providers, and nobody sees that a case is late. The team's evidence register (as cited there) notes that over 40% of people with hypertension in a 2025 UAE screening campaign did not know it (MOHAP, reported by Gulf News).

SOLUTION
Halqa turns each raised reading into one case with eight states, one accountable owner and one due date per step. Overdue, rejected and unowned cases appear in a coordinator queue. A severe reading creates a same-day clinician review. Only a clinician can close a case. Patients get plain-language results in English, Arabic or French, a teach-back check, an SMS thread in Yaoundé and, after treatment starts, one small weekly action that shrinks when a week is missed.

HOW IT MEETS THE SIX POINTS
1. End-to-end visibility: one case per result, eight-step progress, audit timeline, FHIR bundle.
2. Ownership and timely progression: owner and due date on every step, overdue and escalation rules, unreachable-patient protocol.
3. Patient-centred communication: approved templates in three languages, teach-back, red-flag check, consent controls.
4. Cross-provider coordination: referral accept and reject, rejected-referral queue, e-consults.
5. Safe, human-governed escalation: rule-based severe handling, urgent review task, clinician-only closure.
6. Closure and impact measures: closure gate with evidence, live dashboard, simulated baseline against the loop.

WHAT IS REAL AND WHAT IS SIMULATED
Real code with automated tests (suite passed on 20 November 2026): the case engine, closure gate, audit log, consent effects, message validator, and the simulation. Simulated: every person, reading and message; IFHAS, Malaffi, Thiqa, SMS and WhatsApp; insurance cover; and all outcome numbers, which come from a simulation on synthetic people using mostly our own assumptions. They are not evidence of clinical effectiveness.

RESPONSIBLE AI, SAFETY AND DATA GOVERNANCE
Rules decide routing, urgency, ownership and closure. A language model can only re-word approved message text, is off by default, must pass a validator and needs recorded staff approval. Staff cannot send free text. Consent withdrawal stops messages, referral sharing, the lifestyle plan and dashboard inclusion. The dashboard is aggregate only and hides groups under 5 people. The audit log cannot be edited through the application, and on SQLite not through the database either. A safety case lists 16 hazards and residual risks.

ASSUMPTIONS AND LIMITATIONS (THE FIVE THAT MATTER MOST)
1. No clinician has reviewed the pathway. All thresholds and service levels are placeholders pending clinician sign-off.
2. Arabic and French text has not been reviewed by native-speaker clinical reviewers.
3. All integrations are simulated, and no message is really delivered. A patient with no consented channel depends on a coordinator's call.
4. Authentication is demo only, PostgreSQL is unexercised, and there is no load testing or accessibility audit.
5. An independent end-to-end run found defects, now fixed, but did not cover every screen in every language. There is no hosted deployment: the entry is a public repository plus a demonstration video.
The prototype is not a medical device.

PATH TO PILOT
Clinical sign-off of the pathway and wording; safety and data protection assessment; real identity, encryption and consent enforcement; one screening source and one clinic connected; a time-limited pilot with a comparison group. A pilot would measure time to notification, acknowledgement, confirmation and care; referral, appointment and treatment initiation rates; unresolved results and delay reasons; teach-back pass rate and confidence; weekly check-in and re-engagement; and, once defined by clinicians, blood pressure control.

LINKS (REPOSITORY)
README.md; docs/TECHNICAL_DOCUMENTATION.md; docs/SAFETY_CASE.md; docs/DEMO_SCRIPT.md; docs/diagrams/diagrams.md; docs/DECISIONS.md; backend/data/DATA_CARD.md; THIRD_PARTY_NOTICES.md
