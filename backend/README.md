# Ubuntu Voice Backend

FastAPI backend for privacy-first, tenant-scoped RAG support.

See [backend docs](./docs/README.md) for architecture and design decisions.

## Email alerts

Conflict alert emails use SendGrid. Configure both `SENDGRID_API_KEY` and
`SENDGRID_FROM_EMAIL`; the sender address must be verified in SendGrid.
