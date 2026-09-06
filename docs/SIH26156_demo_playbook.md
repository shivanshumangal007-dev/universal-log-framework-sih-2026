# SIH26156 — Universal Log Pre-processing Framework
### Demo Playbook — Internal Hackathon, Sept 7 2026

---

## 1. The pitch (say this in your first 30 seconds)

> "Every SOC and SIEM team faces the same problem: logs come in from hundreds of vendors, in
> formats nobody agreed on in advance — Syslog, JSON, CEF, CSV, and a hundred proprietary
> in-house formats that don't match anything standard. Today, when a new format shows up,
> someone has to write a custom parser by hand before that data is usable.
>
> We built a pipeline that doesn't just parse known formats — it **degrades gracefully**.
> Known formats get parsed instantly. Anything unrecognized doesn't get dropped — it goes
> through an AI-assisted inference engine that proposes a structure and a confidence score,
> and lands in a human review queue instead of a black hole. A human approves or rejects it
> in one click, and approved logs join the same clean, structured store as everything else.
>
> So instead of 'this format isn't supported yet,' the answer is always 'we can already
> ingest it, and a human just needs to confirm the guess.'"

**One-liner if you only get one sentence:** *"A log ingestion pipeline that parses what it
recognizes instantly, and turns what it doesn't recognize into a confidence-scored,
human-reviewable suggestion instead of a dropped log."*

---

## 2. Problem statement mapping (SIH26156)

The PS asks for a **Universal Log Pre-processing Framework** — normalize/parse logs from
diverse sources (Syslog, JSON, XML, CSV, CEF, LEEF, proprietary vendor formats) for
downstream SIEM / data lake / ML ingestion.

Map every part of what you built directly onto this, out loud, during the pitch:

| PS requirement | What we built |
|---|---|
| Parse diverse known formats | Collector → Kafka → **parser chain-of-responsibility**: tries JSON → CEF → Syslog → CSV in order |
| Handle formats we don't recognize in advance | Unmatched lines go to a dedicated `unknown-logs` topic, not dropped |
| Normalize into one usable structure | Everything — known or inferred — lands in ClickHouse in a consistent row shape |
| Support downstream SIEM/data lake/ML use | ClickHouse is queryable directly; `parsed_logs` + approved `review_queue` rows form one clean dataset |
| (Implicit) handle proprietary/unknown vendor formats | The **inference engine** — delimiter detection + field-type guessing + confidence scoring + human approve/reject loop |

---

## 3. What we actually built (say this while the architecture diagram is on screen)

Full path, in order:

1. **Collector** (Go) — tails files and listens for syslog (UDP), publishes every line as a
   `RawEvent` to Kafka's `raw-logs` topic.
2. **Parser** (Go, 2 replicas) — consumes `raw-logs`, tries JSON → CEF → Syslog → CSV in
   order. A match publishes to `parsed-logs`. No match publishes to `unknown-logs` instead
   of being dropped.
3. **Sink** (Go) — consumes `parsed-logs`, batches inserts into ClickHouse's `parsed_logs`
   table with retry/backoff.
4. **Inference** (Python/FastAPI) — consumes `unknown-logs`, runs a sliding per-source
   window through a delimiter + field-type inference engine, scores a confidence, publishes
   to `inferred-logs`.
5. **Inferredsink** (Go) — consumes `inferred-logs`, writes into ClickHouse's `review_queue`
   table with `status: pending`.
6. **Gateway API** (FastAPI, JWT-authed) — lets a human list the review queue, and
   approve/reject each entry. Approving copies the row into `parsed_logs` as
   `format: inferred_approved` — same table everything else lands in.
7. **Dashboard** — the human-facing view of all of the above.

Everything runs as its own Docker container, orchestrated by one `docker-compose.yml`.

**If you only show one diagram, show the parser's format-detection chain** — that's the
single visual that makes a judge go "oh, that's clever" without you having to explain it.

---

## 4. Pre-demo checklist — run this BEFORE judges arrive, not during

- [ ] `docker compose down` then `docker compose up -d --build` — fresh containers, no
      leftover state from last night's debugging session
- [ ] `docker compose ps` — confirm every service shows `Up`, and `kafka`/`clickhouse`
      specifically show `(healthy)`
- [ ] **Decide: wipe old test data or keep it?** Your `review_queue` and `parsed_logs`
      tables currently have debugging leftovers (`test-low`, `test-v2`, duplicate garbage
      lines from restarts). Either:
      - Wipe clean: `docker exec -it ch-server clickhouse-client --password changeme -q "TRUNCATE TABLE logs.parsed_logs"` and same for `logs.review_queue` — gives you a
        pristine "0 rows" starting point to demo from live
      - Or keep it and just don't query those tables until after you've shown fresh data —
        riskier, a judge might ask you to `SELECT *` and see confusing test junk
      **Recommended: wipe clean the night before, not minutes before you're on stage.**
- [ ] Prepare 3–4 test log lines in advance, in a text file you can paste from (don't type
      live, you will typo under pressure) — one clean JSON line, one clean syslog line
      (already flowing from the container's own syslog test), one CEF or CSV line, and one
      deliberately unstructured "vendor-proprietary-looking" line for the inference demo
- [ ] Open 3 terminal tabs in advance: one for `docker compose logs -f parser`, one for
      `kafka-console-consumer` (or skip this one live — it's mostly for your own debugging,
      not audience-friendly), one free for typing commands
- [ ] Open the dashboard (`localhost:3000`) and the ClickHouse rows in a browser tab, logged
      in and ready, before you start talking
- [ ] Have this playbook open on a second screen or phone — don't rely on memory under
      pressure

---

## 5. Live demo script — minute by minute

**Minute 0–1: The pitch** (section 1 above, memorized, said while your architecture SVG is
on screen — not read off the slide).

**Minute 1–2: Show the architecture diagram**, point at each box as you say the 7-step flow
from section 3. Keep this fast — a judge's eyes glaze over on a 5th arrow-following
explanation. This is context-setting, not the main event.

**Minute 2–4: Live known-format demo**
```bash
echo '{"level":"info","msg":"live demo — clean json line"}' >> ./ingestion/configs/test.log
```
Say: *"This is a standard JSON log line — watch it flow through in real time."* Switch to
the dashboard or a ClickHouse query already queued up:
```bash
docker exec -it ch-server clickhouse-client --password changeme -q "SELECT source, raw_line, format, event_timestamp FROM logs.parsed_logs ORDER BY event_timestamp DESC LIMIT 3"
```
Point out `format: json` and the timestamp — proves it's live, not pre-seeded.

**Minute 4–7: The centerpiece — unknown format → inference → human review**
```bash
echo 'VENDOR-X|9921|CRIT|disk_array_2|temp=88C|status=degrading' >> ./ingestion/configs/test.log
```
Say: *"This looks like a real vendor log, but it matches none of our known formats — watch
what happens instead of it just disappearing."*
```bash
curl -s http://localhost:8000/inference/stats | python3 -m json.tool
```
Point out the confidence score. Then switch to the dashboard's review queue screen (or):
```bash
curl -s http://localhost:8000/api/review-queue -H "Authorization: Bearer <token>" | python3 -m json.tool
```
**Then actually click Approve in the dashboard UI live.** This is your strongest visual
moment — a human-in-the-loop decision happening on stage, not just a backend log scrolling
by. Say: *"One click, and this now joins the same clean dataset as everything else — that's
the difference between a dropped log and a system that gets smarter with a human's help."*

**Minute 7–8: Close**
Restate the one-liner from section 1. Mention the fallback chain briefly (JSON → CEF →
Syslog → CSV) as *"already production-shaped, not a prototype hack"* — plural Go
microservices, Kafka as the backbone, ClickHouse for scale, all containerized.

---

## 6. Known limitations — have an honest answer ready, don't get caught off guard

Judges asking sharp questions is a good sign, not a threat — answer plainly, don't over-explain:

- **"How do you guarantee no log is lost if ClickHouse goes down mid-write?"**
  → *"Our sink retries with exponential backoff, and we're aware our current Kafka commit
  timing needs one more pass before we'd call it fully at-least-once — that's on our
  post-hackathon list."* (Honest, shows self-awareness, doesn't overclaim.)
- **"What happens if the same unknown line comes in twice?"**
  → *"Right now each occurrence is scored independently — deduplication isn't built yet,
  it's a natural next step."*
- **"How confident are you in that confidence score?"**
  → *"It's based on structural consistency across a sliding window of recent lines from the
  same source — we specifically tuned it to avoid overconfidence on a single sample, which
  was actually a bug we caught and fixed during testing."* (True, and makes you look
  rigorous rather than defensive.)

---

## 7. Backup plan if live demo breaks on stage

- Have a **screen recording** of the full flow (echo line → inference → dashboard approve)
  recorded the night before, ready to play if Docker/Wi-Fi/anything fails live
- Keep the two architecture SVGs as static images in your slides regardless — they carry the
  explanation even with zero terminal access
- If Kafka/ClickHouse is genuinely down and unrecoverable in the moment, pivot to *"let me
  walk you through it on the architecture diagram and this recording instead"* — smoothly,
  don't panic-debug in front of judges

---

## 8. Fast facts to have loaded in memory

- PS: **SIH26156**, NTRO, Universal Log Pre-processing Framework, Blockchain & Cybersecurity theme
- Stack: Go (collector, parser, sink, inferredsink) + Python/FastAPI (inference + gateway) + Kafka + ClickHouse + Docker Compose
- Formats natively parsed: JSON, CEF, Syslog, CSV
- Formats handled via inference: anything else, with confidence scoring + human review
- Parser runs 2 replicas — mention this if asked about scale ("horizontally scalable by
  design, not just a single script")
