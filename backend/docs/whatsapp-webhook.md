# WhatsApp Webhook

Ubuntu Voice can answer users who message a Twilio WhatsApp number directly, without using the web chat UI.

## Endpoint

Configure Twilio WhatsApp incoming messages to send `POST` requests to:

```text
https://<your-backend-host>/api/v1/webhooks/whatsapp/twilio
```

There is also a compatibility endpoint at:

```text
https://<your-backend-host>/whatsapp-webhook
```

Both endpoints expect Twilio's default `application/x-www-form-urlencoded` payload.

## Environment

Set these backend environment variables:

```text
TWILIO_ACCOUNT_SID=<your Twilio account SID>
TWILIO_AUTH_TOKEN=<your Twilio auth token>
TWILIO_WHATSAPP_NUMBER=whatsapp:+<your Twilio WhatsApp number>
WHATSAPP_SESSION_SECRET=<a separate random secret>
WHATSAPP_SESSION_TIMEOUT_MINUTES=60
```

`TWILIO_WHATSAPP_NUMBER` is used as a fallback sender when Twilio does not include a `To` field.
`WHATSAPP_SESSION_SECRET` derives non-reversible participant identifiers so user phone numbers are
not stored in routing sessions. It falls back to `TWILIO_AUTH_TOKEN` when omitted.

## Agent Routing

One registered WhatsApp number serves every agent currently stored in the `companies` table.
An agent's saved `Company.phone` is contact metadata and does not control WhatsApp routing.

When a WhatsApp webhook arrives:

1. The backend verifies that Twilio's `To` number matches `TWILIO_WHATSAPP_NUMBER`.
2. The user's `From` number is normalized and converted to a keyed hash; the raw number is not stored.
3. A participant's first message always queries the current agents and sends a numbered menu.
4. A valid numeric choice creates a routing session for that participant and selected agent.
5. Later messages run through that agent's tenant-scoped RAG pipeline.
6. Activity refreshes the session. After 60 minutes of inactivity, the next message shows the menu again.

Participants can send `MENU`, `AGENTS`, or `SWITCH` at any time to clear their active selection and
receive the latest agent list. Invalid numeric selections also return the current menu.

If no agents exist, the participant receives a temporary unavailable response. Messages sent to a
different recipient number are acknowledged without a reply.

## Behavior

- Replies use the existing tenant-scoped RAG pipeline.
- Agent menus are generated from current database records in stable creation order.
- Routing sessions store only a keyed participant hash, the registered platform number, the selected
  agent ID, and timestamps.
- General greetings and simple safety reports use the same non-RAG fallback handling as the web chat.
- Conflict-alert email detection still runs before the RAG answer.
- Usage is recorded against the matched agent owner's account.
- Twilio credentials and user phone numbers are never logged.
