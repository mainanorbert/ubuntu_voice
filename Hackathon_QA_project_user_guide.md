# Ubuntu Voice: Functional and Testing Guide

## Table of contents

- [1. What the system does](#1-what-the-system-does)
- [2. How an agent works](#2-how-an-agent-works)
- [3. Creating useful agents](#3-creating-useful-agents)
- [Evaluation datasets and `/test_data`](#evaluation-datasets-and-test_data)
- [4. How users should report an emergency](#4-how-users-should-report-an-emergency)
- [5. Emergency categories and statistics](#5-emergency-categories-and-statistics)
- [6. Emergency answers and notifications](#6-emergency-answers-and-notifications)
- [7. Statistics table and map](#7-statistics-table-and-map)
- [8. Important map limitation](#8-important-map-limitation)
- [9. Correcting statistics](#9-correcting-statistics)
- [10. Web chat and WhatsApp testing](#10-web-chat-and-whatsapp-testing)
- [11. Test constraints and expected limitations](#11-test-constraints-and-expected-limitations)
- [12. Recommended test cases](#12-recommended-test-cases)
- [13. Walkthrough video](#13-walkthrough-video)
- [14. Support](#14-support)

## 1. What the system does

Ubuntu Voice is a low-bandwidth emergency-information and peace-support platform. It connects users to community-defined AI agents that answer questions from trusted documents uploaded for that agent.

The system supports:

- Public web chat without requiring the visitor to log in.
- WhatsApp conversations routed through a configured Twilio number.
- Agent-specific PDF knowledge bases and retrieval-grounded answers.
- Emergency-report classification and regional statistics.
- A statistics table and map for monitoring reported locations and incident statuses.
- Optional email, SMS, and push notifications for urgent conflict alerts.
- Note: SMS, and push notifications for urgent conflict alerts not configured for now
- Signed-in features for creating agents, uploading documents, and reviewing monitoring information. Administrator privileges are needed only for approving agents, editing known places, and correcting statistics.

The system provides information and routing support. It does not replace emergency services, medical care, legal advice, humanitarian verification, or official casualty accounting.

## 2. How an agent works

An agent is a community-specific knowledge base. It may represent a country, region, organization, or subject such as women’s protection, displacement support, or humanitarian assistance.

The normal flow is:

1. An authenticated user creates an agent with a name, contact email, and optional phone number and description.
2. The creator uploads relevant PDF documents for that agent.
3. The system extracts the text, divides it into searchable sections, and creates embeddings.
4. Before approval, the creator tests and evaluates the agent using questions based on its uploaded documents. The creator can use the example files in [`test_data/`](test_data/) or add custom test documents, questions, and reference answers for the agent.
5. The creator improves the documents, instructions, or test data based on the evaluation results and submits the agent for approval.
6. The agent is reviewed and approved before it is made public.
7. Only approved agents appear in the public agent directory and WhatsApp selection menu.
8. A user selects an approved agent and asks a question.
9. The system retrieves relevant excerpts only from that agent’s documents and generates a concise answer.
10. If trustworthy excerpts are unavailable, the agent should say that it does not have enough trusted information instead of inventing facts.

Users may chat with any approved public agent without logging in. Login is required for creating agents, uploading documents, and using signed-in monitoring functions. Existing user access is sufficient for the hackathon. Request administrator access only when an agent needs approval, a known place must be added, edited, deactivated, or corrected, or a statistic must be corrected or deleted.

## 3. Creating useful agents

An agent should have a clearly defined purpose and a document collection that matches that purpose. Useful source material can include:

- Conflict history, timelines, and verified background facts.
- Local laws, constitutional rights, and human-rights procedures.
- Emergency, police, medical, shelter, food, protection, and legal-assistance contacts.
- Information about NGOs, humanitarian agencies, refugee services, and reporting channels.
- Local languages, community terminology, safe-reporting guidance, and eligibility rules.
- Region-specific information such as cities, camps, borders, and service locations.

Do not upload documents containing unnecessary personal data, secrets, passwords, API keys, or unverified claims.

The [`test_data/`](test_data/) directory contains documents for several example agents, together with example evaluation questions and reference answers. After creating an agent and uploading its documents, users can use these files to test and evaluate their own agent before requesting approval. They can also create their own test data using documents and question-and-reference-answer pairs that match the agent's purpose. The sample contacts are suitable for testing the workflow only.

Creators may evaluate an agent while it is pending approval and use the results to improve its documents, instructions, and test data. This private evaluation workflow does not make the agent public; administrator approval is required before the agent is available in the public web directory and WhatsApp menu.

### Evaluation datasets and `/test_data`

Use the [`test_data/`](test_data/) directory when preparing an agent for evaluation. It contains one folder for each example agent. Inside each agent folder, the `evaluation_dataset_samples.md` file contains sample test questions and reference answers that match the documents in that same folder.

For a proper evaluation, select the correct agent from the agent list in `/evaluations`. Add only questions and reference answers that are relevant to that agent and supported by its current uploaded knowledge base. Questions from another agent, or reference answers based on documents that have not been uploaded, will produce misleading evaluation results.

To use the samples:

1. Create or select the matching agent in the application.
2. Upload that agent folder's PDF documents to the agent's knowledge base.
3. Open `/evaluations` and select the matching agent from the agent list.
4. Copy only relevant sample questions and reference answers from that agent's `evaluation_dataset_samples.md` file into the evaluation dataset form.
5. Run the evaluation and review correctness, relevance, groundedness, and retrieval relevance.

For example, use [`test_data/sudan peace agent/evaluation_dataset_samples.md`](test_data/sudan%20peace%20agent/evaluation_dataset_samples.md) with the Sudan Peace Agent documents, and use the equivalent sample file in the Congo or Somalia folder for those agents. Do not mix a question and reference answer from one agent with another agent's documents. The samples are for testing the workflow; operational contacts and facts must be verified before deployment.

## 4. How users should report an emergency

Users should write reports as concrete, factual messages. The most useful report contains:

- What happened.
- Where it happened: before reporting, check `Known places` in the dashboard and use a specific configured city, town, camp, county, or other listed place.
- When it happened, if known.
- The number of people affected, injured, displaced, missing, or dead, if known.
- Any immediate safety concern.

Examples:

- `Severe hunger is affecting families in Nyala; approximately 200 people need food assistance.`
- `Two people were killed in Nyala today.`
- `Families were forced to leave their homes in El Fasher and need shelter.`
- `Armed men assaulted women near Kismayo this morning.`

Avoid unsupported conclusions, rumors, personal names, phone numbers, email addresses, account IDs, and unnecessary identifying details. Do not include sensitive information unless it is essential for a safe response.

A place is required if you want the report’s incident status to be recorded in the statistics and shown on the map. Before reporting, check `Known places` in the dashboard and use one of the configured place names in your report. Reports without a concrete place may still receive an emergency response, but they normally cannot be recorded as a statistics row or displayed as a map status.

## 5. Emergency categories and statistics

The background incident classifier looks for four recordable categories:

| Category | Examples | Stored statistic |
|---|---|---|
| **Rights Violations** | Assault, abuse, denial of rights, attacks on civilians, or other reported violations | Agent, place, sanitized description, and total count |
| **Casualties** | People killed or injured | Agent, place, sanitized description, and total count |
| **Displacements** | Forced movement, refugees, homelessness, or people fleeing an area | Agent, place, sanitized description, and total count |
| **Severe Hunger** | Severe food insecurity, starvation risk, or urgent lack of food | Agent, place, sanitized description, and total count |

Classification runs separately after a web-chat or WhatsApp message passes input guardrails, so it does not intentionally delay the chat reply. The classifier returns structured records, the backend validates the category, removes obvious contact details from the description, normalizes the place name, and saves the result.

For the same agent, place, and category:

- The first valid report creates a row with `total_count = 1`.
- Each later valid report increments that row by one.
- A report mentioning multiple categories can create multiple rows, such as both `Severe Hunger` and `Casualties` for Nyala.
- The count is the number of stored reports, not a verified count of people affected.

Statistics are therefore monitoring indicators and should not be presented as official or independently verified casualty totals.

## 6. Emergency answers and notifications

Emergency messages are treated as support requests. The answer agent prioritizes immediate safety guidance and searches the selected agent’s documents for applicable:

- Rights and procedures.
- Humanitarian, protection, medical, food, shelter, and legal-support organizations.
- Police and emergency-service contacts.
- Reporting channels and safety protocols.

The system must not claim that an authority was contacted, promise a rescue, or invent a local phone number. Users should contact local emergency services or trusted organizations directly when there is immediate danger.

The selected agent’s configured contact email is used for relevant conflict-alert workflows. Alert delivery is optional and depends on configured SendGrid settings. SMS and push notifications through Twilio and Pushover are implemented in the backend, but they are not currently available as user-facing features. They are reserved for future activation and require provider configuration before release. A notification is not guaranteed merely because a report was classified or saved; delivery depends on the alert decision, provider configuration, connectivity, and provider response.

The alert workflow is intended mainly for imminent conflict signals, such as active violence or an attack about to happen. A normal historical question or general request for information should not trigger an alert.

## 7. Statistics table and map

Signed-in users can open the statistics view to see rows containing:

- Agent name.
- Place.
- Sanitized description.
- Incident category.
- Aggregated report count.
- Last update time.

The dashboard also displays category totals and recent reported activity. The map groups records by place and displays separate colored markers for reported categories.

Only reports that contain a recognized place can produce a recorded status and a map marker. To have a report included in the statistics and shown on the map, first check `Known places` in the dashboard and report the incident using a specific place listed there.

Map colors currently represent:

- Red: Rights Violations.
- Orange: Casualties.
- Blue: Displacements.
- Yellow: Severe Hunger.

## 8. Important map limitation

The system does not capture a user’s GPS location and does not geocode the reporter automatically. It matches the reported place name against the `Known places` table and uses the latitude and longitude stored for that known place.

Consequences:

- A report without a place may receive a response but will normally not create a statistics row, incident status, or map marker.
- A report with a place that is not in `Known places` may be saved in the statistics table but will not appear on the map until the place is configured and matched.
- A misspelled or ambiguous place may not match the intended location.
- A marker represents the configured coordinates for a known place, not the exact location of the incident or reporter.
- Several incidents in the same city may appear at the same map point.
- Map points and statistics are not proof that an incident occurred at those coordinates.

Administrator access is required only to open `Manage known places` and add, edit, deactivate, or correct a place’s name, country, latitude, and longitude. Place changes affect future map matching and display. Existing user access is enough for the rest of the hackathon workflow.

## 9. Correcting statistics

Administrator access is required only to edit or delete a statistic row when a classifier result is wrong. Existing user access is enough for viewing statistics and completing the rest of the hackathon workflow. If a statistic needs correction, request the appropriate administrator access by emailing `mainanorbert90@gmail.com`. Include the account email used to sign in and explain which statistic requires correction and why. Do not attempt to modify statistics without the required permission.

After permission is granted, editing allows correction of:

- Place.
- Sanitized description.
- Category.
- Total report count.

The system prevents duplicate rows for the same agent, normalized place, and category. If a matching row already exists, edit that row rather than creating another one. Delete incorrect rows carefully because deletion removes the aggregate record; it does not recover the original report.


## 10. Web chat and WhatsApp testing

### Web chat

1. Open the public chat page.
2. Select an approved agent.
3. Send a general question and verify that the answer is grounded in that agent’s documents.
4. Send a specific emergency report containing a category, place, and number.
5. Wait briefly for background classification.
6. Sign in and verify the statistics row and incident status; if the reported place is configured in `Known places`, verify that the corresponding map marker is displayed.

### WhatsApp

Users can chat with an approved agent through WhatsApp at **+254 106 539 556**.

1. Save **+254 106 539 556** in WhatsApp and open a chat with the number.
2. Send `Hi`, `Hello`, or any first message.
3. The system replies with a numbered list of available approved agents.
4. Reply with the number of the agent you want to use, for example `1`.
5. Wait for the confirmation that you are now chatting with that agent.
6. Send your question or report as a new message. For example: `Severe hunger is affecting families in Nyala; approximately 200 people need food assistance.`
7. The selected agent replies using its approved knowledge base. Emergency reports are also classified in the background for statistics.
8. To choose another agent, send `MENU`, `AGENTS`, or `SWITCH`, then select another number.

For the incident status to be recorded and shown on the map, first check `Known places` in the dashboard, then include the issue and use a specific place listed there. Include any known numbers as well. For example: `Two people were killed in Nyala today` or `Families were displaced from El Fasher and need shelter.`

The first numbered reply is only an agent-selection message and is not classified as an incident. The report must be sent after the agent has been selected. Verify the resulting row in the signed-in statistics table after background processing completes.

`MENU`, `AGENTS`, or `SWITCH` clears the active selection. An expired selection returns the user to the agent menu.

## 11. Test constraints and expected limitations

When testing, remember:

- Background classification is best effort and may be delayed or fail if the model provider, database, or deployment process is unavailable.
- A malformed or unsupported classifier result is rejected rather than written to the database.
- Reports with no concrete place may receive a response but do not normally produce a statistics row, incident status, or map marker.
- Statistics count reports, not people, and repeated reports are not automatically deduplicated across separate messages.
- Agent answers are limited to the selected agent’s uploaded knowledge base.
- Uploaded documents determine answer quality; missing, outdated, contradictory, or fabricated documents produce poor or unsafe results.
- Public chat does not require login. Viewing statistics and creating agents require authentication; administrator access is needed only for approving agents, correcting statistics, and managing known places. Existing user access is sufficient for the hackathon.
- An agent creator cannot make an agent public until it has been approved.
- Notification providers and Google Maps require deployment configuration and may be unavailable in local development.
- The platform should not be used as the sole source for emergency dispatch, official statistics, legal decisions, medical decisions, or security operations.

## 12. Recommended test cases

Evaluate each agent using test questions and their reference answers. A test question should represent something a user may ask about the agent's documents, while the reference answer should describe the facts and key points an accurate answer must contain.

For each question:

1. Submit the question to the correct agent.
2. Compare the agent's response with the reference answer.
3. Check whether the response is factually accurate, complete, relevant, and grounded in the agent's documents.
4. Record incorrect, missing, or unsupported information and use the results to improve the documents, instructions, or test data.

The examples in [`test_data/`](test_data/) can be used as a starting evaluation set. Users should add their own questions and reference answers to test the topics and documents specific to their agents. Agent accuracy should be judged against the reference answer, not only by whether the response is fluent or well written.


Understanding the information above will help you know how best to hack the system and identify bugs.

## 13. Walkthrough video

Watch the [Ubuntu Voice walkthrough video](https://www.youtube.com/watch?v=_O3LJtk8dBo) for a guided demonstration of the platform.

## 14. Support

For agent approvals, known-place or statistics corrections, technical issues, or other inquiries about the Ubuntu Voice app, users can email `mainanorbert90@gmail.com`. Existing user access is sufficient for the hackathon; request administrator access only for agent approval or when one of the two data areas needs editing. Include the account email used to sign in and briefly explain the approval or correction required. Do not include passwords, API keys, or other sensitive credentials in the email.