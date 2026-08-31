# AegisPilot — 4-Minute Demo Script & Run Guide (record-ready)

**Live war room:** https://aegisops-kjacopurja-uc.a.run.app
**Repo:** https://github.com/Sak3th2004/Aegisops

> Judging weights: **Innovation/Utility 40% · Architecture 30% · Demo/Production-readiness 30%.**
> Winning arc: **Polished incident → the judge's own data → it remembers → runs on real Google Cloud.**
> Total run time: **4:00.** Stay tight; going over hurts you. Unedited single take is a plus.

---

## PART 0 — HOW TO RUN IT LIVE (three ways; use #1 for the video)

### 1) The UI way — RECOMMENDED for the demo (no terminal on screen)
Just open the live URL and click. Everything runs from the buttons:
- **https://aegisops-kjacopurja-uc.a.run.app**
- **"Fire Incident"** (top-right) → fires the next rotating scenario (checkout → cart → payments).
- **"Custom"** → judge/you enter your OWN incident (service, logs, deploy, optional screenshot).
- **Approve/Reject** in the modal → the human-in-the-loop gate.
- **"Registry"** → shows the 6 agents + Orchestrator (versions, models, tools).

### 2) The CLI way — if you'd rather fire from a terminal (or let a judge do it)
From the repo root (with the venv active):
```bash
python scripts/publish_alert.py --pubsub                 # rotating scenario via real Pub/Sub → Cloud Run
python scripts/publish_alert.py --scenario cart --pubsub # force a specific one: checkout | cart | payments
python scripts/publish_alert.py --url https://aegisops-kjacopurja-uc.a.run.app   # via HTTP instead
```
Then watch the war room in the browser.

### 3) Run it entirely on your own machine (backup if the internet is flaky on the day)
```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -r backend/requirements.txt
# .env already has your GCP/Vertex config; auth is ADC:
gcloud auth application-default login
uvicorn backend.main:app --port 8080          # backend + serves the built UI at http://localhost:8080
# (optional live-reload UI) cd frontend && npm install && npm run dev  → http://localhost:5173
```
Open http://localhost:8080 and click **Fire Incident**.

---

## PART A — Pre-flight checklist (~15 min before recording)

1. **Warm the service** (kills cold-start lag on camera): open the URL, click **Fire Incident**, approve it, let it resolve. Then hard-refresh (Ctrl+Shift+R) back to the clean idle screen.
2. **Open these tabs in order** (so you just click/Alt+Tab through them):
   1. War room — https://aegisops-kjacopurja-uc.a.run.app  *(leave on the idle "Fire Incident" screen)*
   2. Cloud Run — https://console.cloud.google.com/run/detail/us-central1/aegisops/metrics?project=aegisops-12345
   3. Firestore — https://console.cloud.google.com/firestore/databases/-default-/data?project=aegisops-12345
   4. Pub/Sub — https://console.cloud.google.com/cloudpubsub/subscription/list?project=aegisops-12345
   5. Slack — the channel your webhook posts to
3. **Clean screen:** full-screen browser (F11), hide bookmarks, Do-Not-Disturb on, phone silent.
4. **Record:** OBS Studio (free) or Loom → **1080p / 30fps**, browser window + mic. Test mic once.
5. **Timing reality:** the pipeline reaches the **Approve** prompt in ~45–60s (real Gemini calls); the RCA (Gemini **Pro**) lands ~30s after RESOLVED. **Never sit silent — narrate the agents while they think.**
6. The **Custom** modal is **pre-filled** with a realistic `auth-svc` incident — you just click **Run incident** (edit it live if you want to prove it's real).

---

## PART B — THE 4:00 SCRIPT (minute-by-minute)

> **[ACTIONS]** in brackets · "spoken narration" in quotes. Speak calmly; let visuals breathe.

### 0:00–0:20 — Hook (idle screen showing)
> "This is **AegisPilot** — an autonomous SRE that works the entire 3am on-call loop. When a production alert fires, six specialized AI agents triage it, diagnose the logs, **read the Grafana dashboard with vision**, find the bad deploy, propose a fix, and — with one human approval — remediate and write the postmortem. It runs on **Google ADK**, **Gemini 3.5 Flash and Pro on Vertex AI**, **Firestore**, **Pub/Sub**, and **Cloud Run**. Here's a live incident."

### 0:20–0:22 — Fire it
> **[CLICK "Fire Incident".]** "An alert just hit our event bus."

### 0:22–1:10 — The agents work (narrate the live pipeline)
> **[Point at the agent graph lighting up, then the reasoning stream on the left.]**
> "The orchestrator hands off between agents — and every line you see is a **real Gemini call**, streamed live with token and latency counts. **Triage** called it a **SEV1** on checkout-svc."
> **[Point at the Diagnosis tab — the Grafana image with the AI annotation overlaid.]**
> "Here's the multimodal part: Diagnosis sent this **actual Grafana screenshot to Gemini vision**, which confirmed the spike — that caption is the AI's own annotation."
> **[Point at Correlation + Memory.]**
> "**Correlation** tied it to a deploy that shipped ~12 minutes ago — **checkout-svc v2.4.1** — with a calibrated confidence. And **Memory** recognized the fingerprint: *seen before, resolved by rollback in about four minutes.*"

### 1:10–1:40 — The human-in-the-loop gate (the differentiator)
> **[Approval modal appears.]**
> "Now the governance gate. AegisPilot **will not touch production on its own** — it proposes a **rollback to v2.4.0**, low-risk and reversible, and **halts for a human**. The destructive action is never something the model can trigger itself."
> **[CLICK "Approve".]** "I approve — the executor runs the rollback, step by step."
> **[Status → RESOLVED; point at resolution time.]** "Resolved — autonomously, in about a minute."

### 1:40–2:00 — Close the loop (RCA + Slack)
> **[CLICK the "RCA" tab; scroll briefly if rendered — else say the line and switch to Slack.]**
> "It auto-wrote the full postmortem with **Gemini Pro** — summary, root cause, timeline, follow-ups."
> **[Alt+Tab to Slack.]** "…posted a **PII-scrubbed incident card to Slack**, and filed a ticket. The whole loop, closed."

### 2:00–2:10 — Bring your own data (set up the wow)
> **[Back to the war room. CLICK "Custom".]** "But none of this is scripted — **you** can hand it your own incident."

### 2:10–2:55 — The judge's own incident (real input)
> **[Form pre-filled with `auth-svc` — point at the log lines.]**
> "A different service — **auth-svc** — with **real log lines**: JWT signature failures after a key rotation. You could paste your own, or even **upload a dashboard image** for the vision agent. I'll run it."
> **[CLICK "Run incident". Narrate as it works.]**
> "Same six agents — reasoning over **this** data now. Diagnosis is classifying **these** logs… Correlation is blaming the **auth-svc v3.2.0** deploy I gave it…"
> **[Approval modal → CLICK "Approve".]** "…proposes the rollback, I approve, it resolves. Nothing pre-baked — it diagnosed exactly what we entered."

### 2:55–3:20 — It learns
> **[Point at the Memory line for this incident.]**
> "And the payoff: **AegisPilot learns.** Every resolved incident is written back to memory — so when this fingerprint returns, the Memory agent **recalls it** and hands responders the known fix instantly. It gets smarter every time it's used."

### 3:20–3:55 — Real Google Cloud (REQUIRED proof)
> **[Alt+Tab: Cloud Run.]** "It's all live on Google Cloud — here's the **Cloud Run** service."
> **[Alt+Tab: Firestore.]** "Every incident and every agent step is persisted in **Firestore** — the real audit trail."
> **[Alt+Tab: Pub/Sub.]** "Alerts arrive via a real **Pub/Sub** push subscription; Gemini runs on **Vertex AI**."

### 3:55–4:00 — Close
> "**AegisPilot** — a real, governed, **learning** multi-agent SRE, live on Google Cloud. Thanks for watching."

---

## PART C — Dry-run rehearsal (do 1–2 full run-throughs first, un-recorded)

1. Run the whole thing once and **time it**; note how long the pipeline takes to reach **Approve** on the day so your narration fills the gap.
2. Muscle-memory the **Alt+Tab order**: war room → Slack → war room → Cloud Run → Firestore → Pub/Sub.
3. If you talk faster than the agents, **slow down** and describe each agent. Never go silent.
4. Under 4:00? Add one architecture sentence ("six agents, each with its own tools and prompt, coordinated by an ADK Runner"). Over? Skip the RCA-tab scroll, show only Slack.

---

## PART D — Contingencies (don't panic on camera)

- **Cold-start pause?** You warmed it in pre-flight. If it ever happens: "spinning up on Cloud Run" — 2–3s.
- **A brief retry flickers?** That's the **503-safe retry wrapper** working — call it out: "it just auto-retried a throttle; the demo can't crash."
- **Incident ends FAILED?** Click **Fire Incident** again — idempotent. (Won't happen warm.)
- **RCA not ready when you open the tab?** It's on Gemini Pro (~30s) — say "auto-generating the postmortem" and show **Slack** (posts quickly).
- **Approve fast** — within a few seconds of the modal appearing — to stay on time.

---

## PART E — WHAT NOT TO DO
- Don't show code editors or raw terminals full of logs — show the **product working**.
- Don't narrate setup or apologize for anything. **Confidence sells.**
- Don't go over 4:00. Don't fake anything — the rollback executor is a clean, clearly-labeled **simulation**; never claim it hits real prod infra.

---

## PART F — Devpost submission checklist
- [ ] Project named **AegisPilot** + tagline (below)
- [ ] Live URL: https://aegisops-kjacopurja-uc.a.run.app
- [ ] Public repo: https://github.com/Sak3th2004/Aegisops (+ README)
- [ ] Architecture diagram (ARCHITECTURE.md — Mermaid renders on GitHub)
- [ ] ~4-min **unedited** video (unlisted/public YouTube), **GCP consoles shown**
- [ ] Write-up: features, Google stack (ADK, Gemini 3.5 Flash/Pro on Vertex, Firestore, Pub/Sub, Cloud Run), governance + learning differentiators
- [ ] Bonus: dev.to/Medium post + LinkedIn/X post with **#AllThingsAgenticHackathon**
- [ ] Submit with buffer — not at the deadline

### Tagline
> *AegisPilot: an autonomous, human-governed multi-agent SRE that diagnoses incidents with multimodal Gemini, learns from every resolution, and runs entirely on Google Cloud.*
