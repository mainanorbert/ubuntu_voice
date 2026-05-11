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
```

`TWILIO_WHATSAPP_NUMBER` is used as a fallback sender when Twilio does not include a `To` field.

## Agent Routing

Each agent is matched by its saved `Company.phone` value. Store the phone as a bare E.164 number:

```text
+15551234567
```

When a WhatsApp webhook arrives:

1. The webhook reads Twilio's `To` field, for example `whatsapp:+15551234567`.
2. The service normalizes it to `+15551234567`.
3. The backend finds the single company whose `phone` matches that number.
4. The existing RAG pipeline runs with that company's documents only.
5. The reply is sent back to Twilio's `From` number through the Messages API.

If no unique agent matches the inbound number, the webhook returns `OK` without sending a reply. This prevents a message sent to one WhatsApp number from being answered by the wrong agent.

## Behavior

- Replies use the existing tenant-scoped RAG pipeline.
- General greetings and simple safety reports use the same non-RAG fallback handling as the web chat.
- Conflict-alert email detection still runs before the RAG answer.
- Usage is recorded against the matched agent owner's account.
- Twilio credentials and user phone numbers are never logged.
