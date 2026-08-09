# Ubuntu Voice: Functional and Testing Guide

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
- Signed-in features for creating agents, uploading documents, and reviewing monitoring information. Administrator privileges are required for approving agents, viewing guardrail audit events, managing places, and correcting statistics.

The system provides information and routing support. It does not replace emergency services, medical care, legal advice, humanitarian verification, or official casualty accounting.

## 2. How an agent works

An agent is a community-specific knowledge base. It may represent a country, region, organization, or subject such as women’s protection, displacement support, or humanitarian assistance.

The normal flow is:

1. An authenticated user creates an agent with a name, contact email, and optional phone number and description.
2. The creator uploads relevant PDF documents for that agent.
3. The system extracts the text, divides it into searchable sections, and creates embeddings.
4. An administrator reviews and approves the agent.
5. Only approved agents appear in the public agent directory and WhatsApp selection menu.
6. A user selects an approved agent and asks a question.
7. The system retrieves relevant excerpts only from that agent’s documents and generates a concise answer.
8. If trustworthy excerpts are unavailable, the agent should say that it does not have enough trusted information instead of inventing facts.

Users may chat with any approved public agent without logging in. Login is required for creating agents, uploading documents, and using signed-in monitoring functions. Only administrators can approve newly created agents, view the `/guardrails` audit page, edit `Known places`, or manage statistics. The `Guardrails` dashboard navigation button is shown only to administrators, and non-administrators cannot access the page by entering its URL directly. Administrator access is granted only to account emails listed in the backend `.env` file's `ADMIN_EMAILS` setting. Users who need these privileges should email `mainanorbert90@gmail` and include their account email.

## 3. Creating useful agents

An agent should have a clearly defined purpose and a document collection that matches that purpose. Useful source material can include:

- Conflict history, timelines, and verified background facts.
- Local laws, constitutional rights, and human-rights procedures.
- Emergency, police, medical, shelter, food, protection, and legal-assistance contacts.
- Information about NGOs, humanitarian agencies, refugee services, and reporting channels.
- Local languages, community terminology, safe-reporting guidance, and eligibility rules.
- Region-specific information such as cities, camps, borders, and service locations.

Do not upload documents containing unnecessary personal data, secrets, passwords, API keys, or unverified claims.

The [`test_data/`](test_data/) directory contains documents for several example agents, together with example evaluation questions and reference answers. Users can use these examples to test and evaluate their agents, or create their own test data using documents and question-and-reference-answer pairs that match their agent's purpose. The sample contacts are suitable for testing the workflow only; they must be replaced with verified operational contacts in a real deployment.

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

Only administrators can open `Manage known places` to add, edit, deactivate, or correct a place’s name, country, latitude, and longitude. Place changes affect future map matching and display.

## 9. Correcting statistics

Only administrators can edit or delete a statistic row when a classifier result is wrong. Editing allows correction of:

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
- Public chat does not require login. Viewing statistics and creating agents require authentication; approving agents, viewing `/guardrails` audit events, correcting statistics, and managing known places require administrator privileges. The `Guardrails` navigation button and `/guardrails` page are available only to emails configured in the backend `.env` file's `ADMIN_EMAILS` setting.
- An agent creator cannot make an agent public without administrator approval.
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

The following workflow checks can also be used to verify the agent and platform behavior:

1. A greeting: verify a short response and no incident statistic.
2. A document-specific question: verify retrieval from the selected agent only.
3. A report with one category and one place: verify one new row.
4. A report with two categories and one place: verify two rows.
5. A repeated report for the same place and category: verify that the count increments.
6. A report with no place or an unknown place: verify that it may not produce a status or map marker; confirm that an unknown place may be saved in the table without appearing on the map.
7. A report containing a phone number or email: verify that stored descriptions are sanitized.
8. An imminent conflict message: verify configured alert behavior without assuming delivery.
9. An unapproved agent: verify that it is unavailable to public web and WhatsApp users.
10. A corrected statistic and known place: verify that the table and map refresh correctly.

For any inquiries or support, users can contact `mainanorbert90@gmail.com`.
