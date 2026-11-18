# Halqa

Halqa (Arabic for "loop") is a hackathon prototype that follows a raised blood pressure reading from screening to care. One raised reading becomes one case with eight states, one accountable owner and one due date at each step, so that overdue, rejected and unowned cases are visible and nobody is lost between providers. Rules decide routing, urgency, ownership and closure, a language model can at most re-word approved message text (off by default), and only a clinician can close a case.

It answers Future Health Digital Innovation Challenge, Population Health, Challenge 05 "Closing the Screening-to-Care Loop", with Challenge 09 lifestyle features as the follow-up stage. Entry by Team Latitude-IT.

> **What is simulated**
>
> - Every person, reading, provider and message is synthetic. There is no real personal data anywhere.
> - IFHAS, Malaffi, Thiqa, SMS and WhatsApp are simulated. Nothing is connected to a real system and no message is really delivered.
> - All thresholds and service levels are placeholders pending clinician sign-off. No clinician has reviewed the pathway.
> - Outcome results come from a simulation on synthetic people, mostly using our own assumptions. They are not evidence of clinical effectiveness.
> - The optional AI re-wording was tested only with mocked HTTP calls and is off by default.
> - The prototype is not a medical device and has not been assessed against any medical device regulation.

## Quick start

The backend runs in Docker inside WSL through the helper script (run from any shell):

```
wsl -e bash /mnt/d/Projects/Hackathon/dev/run.sh build
wsl -e bash /mnt/d/Projects/Hackathon/dev/run.sh up 8000
```

Open `http://localhost:8000/api/docs` for the API. To work on the front end:

```
cd frontend
npm ci
npm run dev
```

The front end serves on `http://localhost:5173` and proxies `/api` to port 8000. `npm run build` writes `frontend/dist`, which the API then serves at `/`. The root `Dockerfile` builds both into one image. Full instructions, environment variables and the production image are in section 12 of the technical documentation.

## Demo personas

All are fictional. Choose one on the landing page ("Continue as Guest"). "Reset demo data" restores the seed. The demo bar has "+1 day" and "+3 days" buttons to move the demo clock.

| Persona | Who |
|---|---|
| `patient_auh` | Khalid, 34, Abu Dhabi, flagged at a simulated screening, 152/96. Arabic or English |
| `coordinator_auh` | Mariam, care coordinator, Abu Dhabi. Sees the queue |
| `clinician_pcp` | Dr Sara, family medicine. Reviews, refers, answers e-consults, closes |
| `clinician_specialist` | Dr Omar, hypertension clinic. Accepts or rejects referrals |
| `patient_yde` | Jean-Paul, 47, Yaounde, clinic reading 164/102. French, SMS and WhatsApp thread |
| `nurse_yde` | Clarisse, nurse coordinator, Yaounde |
| `analyst` | Programme analyst. Aggregate dashboard only |

## Repository map

| Path | Contents |
|---|---|
| `backend/app/engine/` | Pure rule engine: states, urgency, service levels, closure gate, lifestyle plan, `config.yaml` |
| `backend/app/api/` | FastAPI routes, role checks, schemas |
| `backend/app/wording/` | Approved templates in English, Arabic and French, validator, optional re-wording |
| `backend/app/fhir/` | Read-only FHIR bundle of a case |
| `backend/app/sim/` | Synthetic cohort and pathway simulation |
| `backend/app/demo/` | Demo clock, seed data, reset |
| `backend/app/db/` | SQLAlchemy models and session |
| `backend/data/` | Synthetic cohorts, simulation results, demo series, data card |
| `backend/tests/`, `backend/tests_data_ai/` | Automated tests |
| `frontend/src/` | React single-page app: shell, design system, i18n, feature screens |
| `docs/` | Documentation, specification, diagrams, OpenAPI file |
| `dev/` | Development helper for Docker in WSL |
| `Dockerfile` | Production image: API and built front end in one container |

## Documentation

- [Technical documentation](docs/TECHNICAL_DOCUMENTATION.md): architecture, case model, clinical boundaries, responsible AI, data, governance, simulation, interoperability, testing, assumptions and limitations, how to run.
- [Safety case](docs/SAFETY_CASE.md): hazards, controls and residual risk.
- [Specification](docs/SPEC.md) and [decisions](docs/DECISIONS.md): the build contract and the recorded deviations.
- [Data card](backend/data/DATA_CARD.md): how the synthetic data is generated.
- [Diagrams](docs/diagrams/diagrams.md): architecture, lifecycle, severe escalation, AI boundary, closure gate.
- [Third-party notices](THIRD_PARTY_NOTICES.md): open-source dependencies and licences.

## Testing

```
wsl -e bash /mnt/d/Projects/Hackathon/dev/run.sh test tests tests_data_ai -q
```

On 2026-11-18 this gave `346 passed, 1 warning in 44.93s`. The tests cover the engine, the API, the wording validator and the simulation. There is no front-end test suite. See section 10 of the technical documentation for what is and is not tested.

## Synthetic data statement

All data in this repository is synthetic and generated by our own seeded code. No real patient, clinician or personal data was used. Names, phone numbers and organisations in the demo are invented. Names of real organisations appear only as labels of simulated sources.

Licence: to be confirmed by the team
