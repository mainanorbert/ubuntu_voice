# Color Palette

The following color palette should be used consistently throughout the application to maintain a professional, accessible, and cohesive user interface.

| Purpose | Color | Hex Code |
|---------|-------|----------|
| **Primary** | Trust Blue | `#2563EB` |
| **Secondary** | Navy | `#1E3A8A` |
| **Accent** | Sky Blue | `#60A5FA` |
| **Background** | Off White | `#F8FAFC` |
| **Emergency / Danger** | Red | `#DC2626` |

## Usage Guidelines

- **Primary (`#2563EB`)** – Use for primary buttons, links, active navigation items, and key interface elements.
- **Secondary (`#1E3A8A`)** – Use for headers, secondary actions, navigation bars, and supporting UI components.
- **Accent (`#60A5FA`)** – Use to highlight important information, hover states, badges, and interactive elements.
- **Background (`#F8FAFC`)** – Use as the default page and content background to provide a clean and modern appearance.
- **Emergency / Danger (`#DC2626`)** – Use only for destructive actions, critical alerts, validation errors, and emergency-related content.

# Development and Quality Assurance Guidelines

When implementing new features, modifying existing functionality, or writing code, ensure the following standards are consistently followed.

## 1. Responsive Design

- Design and implement all user interfaces to work seamlessly across desktop, tablet, and mobile devices.
- Ensure layouts adapt correctly to different screen sizes without breaking.
- Prevent text overflow, overlapping elements, and horizontal scrolling.
- Verify that images, tables, cards, forms, and navigation components resize appropriately.

---

## 2. User-Friendly Error Handling

- Display clear, concise, and actionable error messages.
- Never expose technical details such as stack traces, SQL errors, API exceptions, or internal server messages to users.
- Guide users on how to resolve the issue whenever possible.
- Log technical errors internally while presenting user-friendly feedback in the interface.

---

# Core Functionality Validation

Every feature must be verified to ensure complete end-to-end functionality.

## User Journeys

Validate that all critical workflows function correctly from start to finish, including but not limited to:

- User registration
- User login and authentication
- Password reset (where applicable)
- Dashboard navigation
- Profile management
- CRUD operations (Create, Read, Update, Delete)
- Logout process

All journeys should complete successfully without crashes, unexpected behavior, or data loss.

---

### Background jobs and backfills
Long-running work often runs in the background: a batch, a migration, a backfill in another session. Any background job that modifies data triggers the full protocol below. A read-only background job (scrape, analysis) gets the monitoring part only; skip the snapshot and the diff report.

Monitor it, don't fire-and-forget. While the job runs, post a progress update at least every 5 minutes. Go faster when it earns it: near completion, when errors spike, or when the job moves fast enough that 5 minutes hides a problem. Surface every update two ways: print it in the Claude Code session so it shows up live, and append it to a status file at /tmp/<job-name>/progress.log, timestamped. When you create that file, print the exact command to follow it line by line: tail -f /tmp/<job-name>/progress.log. Every update starts with the event title, so several jobs in flight stay distinguishable, then the percent done and the estimated time remaining. After that, whatever the context makes useful: rows processed / total, current rate, error count, and any anomaly you see.

Progress percent, rate, and ETA are deterministic. Do not eyeball them in latent space. Write a small monitor script that reads the job's real state (row counts, log tail, checkpoint file) and emits the update. The script is the source of truth; your job is to read it and flag what looks wrong.

Snapshot before you touch anything. By default, save every row the backfill will modify to /tmp/ before it runs. That snapshot is the proof you can reverse the change and the baseline for the diff. If the snapshot would exceed 100k rows or 100MB, stop and ask Julien for permission before snapshotting; do not start the job until he answers.

On completion, produce the report. Every backfill ends with a written report on what changed:

- A verdict: did the backfill work? State it plainly, with evidence.
- Whether it needs to be better, and if so why and how. No vague "could be improved": name the specific gap and the fix.
- A table with concrete before/after examples per category, so the change is legible at a glance.
- A full before/after CSV written to /tmp/. Print the exact path in your final report.

Everything for the job (status log, snapshot, report, CSV) lives under /tmp/. Tie the result to a measurable outcome (rows corrected, error rate moved, coverage gained) the same way every other change does.

## Forms and Input Validation

Ensure every input field consideres quality issues such as:

- Empty values
- Valid inputs
- Invalid formats
- Boundary values
- Excessively long inputs
- Special characters where applicable

Ensure that:

- Required fields are enforced and indicated with *.
- Validation messages are clear and understandable.
- Invalid submissions never reach the backend unnecessarily.
- Data integrity is maintained.


# Performance and Reliability

## Performance Testing

Verify that:

- Pages load efficiently.
- API requests complete within acceptable response times.
- Large datasets render without noticeable lag.
- Loading indicators appear while data is being fetched.
- Lazy loading or pagination is implemented where appropriate.



## Error State Validation

Test common failure scenarios, including:

- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 500 Internal Server Error
- API timeouts
- Network interruptions

Ensure every error state:

- Displays a meaningful message.
- Provides recovery options where applicable.
- Does not leave the application in a broken or unusable state.
- If you find developer like errors like 'Could not reach the API server. Is the backend running?' change them

---

# Accessibility

Ensure the application follows basic accessibility best practices:

- Sufficient color contrast.
- Keyboard navigability.
- Proper form labels.
- Semantic HTML.
- Descriptive button and link text.
- Visible focus indicators.
- Appropriate ARIA attributes where necessary.

---

# Code Quality

Ensure that:

- Code is clean, readable, and maintainable.
- Naming conventions are consistent.
- Components are reusable where appropriate.
- Dead or unused code is removed.
- No unnecessary duplication exists.
- Code follows project standards and best practices.
- Appropriate comments are included only where they improve understanding.

---

# Security Validation

Verify that:

- User input is properly validated and sanitized.
- Sensitive information is never exposed.
- Authentication and authorization are enforced correctly.
- Protected routes cannot be accessed without permission.
- Secrets, tokens, and API keys are never hardcoded.

---

# QA Compliance

Before considering any feature complete, verify that it passes all quality assurance checks.

If any implementation does not meet these standards:

1. Identify the issue clearly.
2. Explain why it fails QA requirements.
3. Recommend the appropriate code or design changes.
4. Implement the necessary improvements before marking the work as complete.

No feature should be considered complete until it satisfies all functional, usability, responsiveness, accessibility, performance, reliability, and security requirements.
