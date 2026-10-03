# Fareline

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Fareline is the MHacks 2026 commute-split agent. Interns share a multi-stop Uber or Lyft. Whoever had the cheapest price pays, and the fare is split evenly. Riders change day to day. Fareline lives in the group chat and tracks who owes whom. It does not book the car.

The same ledger answers the test chat, Photon Spectrum iMessage, and the Fetch.ai agent.

**Agent name:** Fareline
**Requested Agentverse handle:** `fareline`
**Address:** not registered in this environment. With `AGENT_SEED` set, `python -m commute_split.fetch_agent` prints the `agent1q…` address. Paste that address here before judging.

## Demo script

Roster: Adrian, Alex, Sam, Riley. "Today" is America/New_York.

1. Adrian: `I paid $48, Alex and Sam rode.` → Alex owes Adrian $16.00, Sam owes Adrian $16.00. Riley is even.
2. Alex: `I just paid Adrian $16.` → Alex and Adrian are even. Sam still owes Adrian $16.00.
3. Sam: `What do I owe?` → Sam owes Adrian $16.00.
4. Alex: `I'm out.` Riley: `I'm in.` → balances stay the same.

A $45 payback that is larger than the debt flips the net. A $50 fare across three riders splits in integer cents (largest remainder, payer first, then named riders). Shares differ by at most one cent and sum to the fare.

## Run the test chat

```bash
uv sync --extra dev
uv run commute-split
```

Open http://127.0.0.1:47291 . Pick who is speaking, then send a line. The SQLite file is `data/commute.db` (override with `COMMUTE_DB_PATH`). Port override: `COMMUTE_PORT`.

```bash
uv run pytest
cd spectrum && npm test
```

## What the chat understands

The sender is known. The test chat has a sender picker. iMessage and ASI:One map an identity onto a rider.

- `I'm in` / `I'm out` — RSVP for today. Balances do not change.
- `I paid $48, Alex and Sam rode.` — the sender paid and rode, plus each named rider. Names dedupe, case-insensitive. New names are added. The sender's share is already paid. Each other rider owes the sender their share.
- `I paid $48` — split across people marked in today, including the sender. If nobody else is in, Fareline says so and does not invent a charge.
- `I just paid Alex $45.` — reduces what the sender owes Alex. Extra money flips the net.
- `What do I owe?` — pairwise net for the sender.

After a fare or payback, the reply repeats who paid, how much, the split or settlement, and the new pairwise nets.

If `ASI1_API_KEY` is set, a line that does not match those forms is sent to ASI:One (`https://api.asi1.ai/v1`, model `asi1`) and rewritten into one canonical line, then applied to the ledger. Recognized lines never call the model. Without the key, Fareline replies with the forms it accepts.

## Environment

Copy `.env.example`. Do not commit real values.

| Variable | Used by | Required |
| --- | --- | --- |
| `COMMUTE_PORT` | test chat | no, default `47291` |
| `COMMUTE_DB_PATH` | all three entry points | no, default `data/commute.db` |
| `SPECTRUM_PROJECT_ID` | Spectrum | yes, to connect iMessage |
| `SPECTRUM_PROJECT_SECRET` | Spectrum | yes, to connect iMessage |
| `SPECTRUM_SENDER_MAP` | Spectrum | yes, so a phone maps to a rider |
| `COMMUTE_API_URL` | Spectrum | no, default `http://127.0.0.1:47291` |
| `AGENT_SEED` | Fetch.ai agent | yes, to register |
| `UAGENT_PORT` | Fetch.ai agent | no, default `8011` |
| `FETCH_SENDER_MAP` | Fetch.ai agent | yes, so an ASI:One address maps to a rider |
| `ASI1_API_KEY` | paraphrase fallback | no |

Spectrum reads `SPECTRUM_PROJECT_ID` and `SPECTRUM_PROJECT_SECRET`, which is what the Stable SDK reads when you omit them in code. This adapter passes them explicitly. Stable docs: https://photon.codes/docs/spectrum-ts/getting-started

## Spectrum iMessage

Adapter: `spectrum/index.js`. It posts every inbound text into `POST /api/messages` with `source: "spectrum"` and sends the ledger reply back into the iMessage space.

```bash
# terminal 1
uv run commute-split
# terminal 2, after the variables above are exported
cd spectrum && npm install && npm start
```

Without `SPECTRUM_PROJECT_ID` and `SPECTRUM_PROJECT_SECRET`, `npm start` exits and explains what is missing. The test chat does not start Spectrum.

An iMessage sender that is not in `SPECTRUM_SENDER_MAP` gets a reply and does not change the ledger. The map is a JSON object of sender id (or display name) to rider name, for example `{"+15551234567":"Adrian"}`.

## Fetch.ai agent

`python -m commute_split.fetch_agent` runs a uAgent (`uagents==0.25.5`) with the Agent Chat Protocol, `mailbox=True`, and `publish_agent_details=True`. A text message calls the same ledger as the test chat. A fare or payback writes `COMMUTE_DB_PATH`. An address missing from `FETCH_SENDER_MAP` does not write.

Registration was not completed here because `AGENT_SEED` is not available and this environment has no Agentverse login. To finish it, follow the Innovation Lab chat-protocol guide: https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents

1. Create an Agentverse account so the mailbox can connect.
2. Export `AGENT_SEED` (do not commit it) and `FETCH_SENDER_MAP`.
3. Run `python -m commute_split.fetch_agent` and leave it running.
4. Copy the `agent1q…` address from the log into this README.
5. Open the inspector URL from that log, choose Connect, then Mailbox.
6. Confirm the log says the agent registered as a mailbox agent and that `AgentChatProtocol` published.
7. From ASI:One, chat with Fareline. `I paid $48, Alex and Sam rode.` must change the SQLite file, not a hard-coded reply.

Hackpack used for this build: https://www.fetch.ai/events/hackathons/mhacks-2026/hackpack (the shorter https://www.fetch.ai/events/hackathons/hackpack path returns 404).

## Submission (human)

From the hackpack's submission document, https://docs.google.com/document/d/1UDW-X1C24hxZviFOQzjTeh0pXRNAoflMb8lhJqZP9Z0 . Video linked from the hackpack: https://drive.google.com/file/d/1EDfKrM7l8soO-40eKkPYDAEkRUTwQKyf/view?usp=sharing

1. Submit the project through Devpost.
2. Also register through the MHacks ASI:One Submission Agent. The hackpack links the festival entry at https://asi1.ai/auth/signup?returnTo=%2Ffestival%2Fmhacks2026%2Fdashboard%3Futm_source%3Dmhacks2026

Before starting, copy an ASI:One shared chat URL (`https://asi1.ai/shared-chat/...`: open the chat, search icon in the left sidebar, under Current chat click Share chat) and each Agentverse profile URL (`https://agentverse.ai/agents/details/agent1q.../profile`).

Team lead, in ASI:One, message MHacks Submission Agent (`Hi` or `I want to submit` works):

1. On the welcome card, click **Create team (I'm the lead)**.
2. Fill in project name, table number (optional), your name, your email, team size including you (1–4), the problem, the public GitHub URL, and the demo video URL (optional).
3. Optional bonus: how many agents, agent profile URLs separated by commas, how many shared chats, shared chat URLs separated by commas.
4. Click **Continue to review**.
5. **Confirm submission**, or **Edit details** and review again.
6. Share the Team ID (for example `mhacks-......`) with teammates.

Teammates message MHacks Submission Agent, click **Join with Team ID**, enter the id, then name and email, then **Join team**.

Status `Incomplete` means details are saved and teammates have not all joined. `Submitted` means every teammate has joined. The lead can click **Edit details** until the deadline.

This environment cannot sign into ASI:One or Devpost, so those two submissions are still open.
