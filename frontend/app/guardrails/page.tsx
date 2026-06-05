"use client"

import { Loader2, RefreshCw } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { DashboardShell } from "@/components/dashboard-shell"
import { Button } from "@/components/ui/button"

type GuardrailEventResponse = {
  id: string
  user_id: string | null
  event_type: string
  action: string
  matched_rules: string[]
  prompt_text: string | null
  response_text: string | null
  input_token_count: number | null
  created_at: string
}

// Formats integer counts.
function format_count(value: number): string {
  return new Intl.NumberFormat().format(value)
}

// Formats ISO datetimes into a short local timestamp.
function format_timestamp(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

// Masks a user identifier so the page never exposes the full raw value.
function mask_user_id(user_id: string | null): string {
  if (!user_id || user_id.trim().length <= 8) return "Hidden user"
  const trimmed_user_id = user_id.trim()
  return `${trimmed_user_id.slice(0, 4)}...${trimmed_user_id.slice(-4)}`
}

// Returns styling for a guardrail action badge.
function action_badge_class(action: string): string {
  if (action === "blocked") return "bg-destructive/15 text-destructive"
  if (action === "monitored") return "bg-amber-500/15 text-amber-700 dark:text-amber-400"
  return "bg-muted text-muted-foreground"
}

// Truncates long prompt and response text for compact table display.
function truncate_text(value: string | null, max_chars = 160): string {
  if (!value) return "Not available"
  const trimmed_value = value.trim()
  return trimmed_value.length <= max_chars ? trimmed_value : `${trimmed_value.slice(0, max_chars)}...`
}

export default function GuardrailsPage() {
  const [events, set_events] = useState<GuardrailEventResponse[]>([])
  const [loading, set_loading] = useState(true)
  const [refreshing, set_refreshing] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const [expanded_event_id, set_expanded_event_id] = useState<string | null>(null)

  /**
   * Loads recent guardrail audit metadata without exposing raw user content.
   */
  const load_events = useCallback(async (mode: "initial" | "refresh") => {
    if (mode === "initial") {
      set_loading(true)
    } else {
      set_refreshing(true)
    }
    set_error(null)
    try {
      const response = await fetch("/api/monitoring/guardrail-events?limit=50")
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) return set_error("Unable to load guardrail events.")
      if (!Array.isArray(data)) return set_error("Unexpected guardrail events response.")
      set_events(data as GuardrailEventResponse[])
    } catch {
      set_error("Network error while loading guardrail events.")
    } finally {
      set_loading(false)
      set_refreshing(false)
    }
  }, [])

  useEffect(() => {
    const timeout_id = window.setTimeout(() => void load_events("initial"), 0)
    return () => window.clearTimeout(timeout_id)
  }, [load_events])

  return (
    <DashboardShell title="Guardrails" description="Review recent safety events without exposing raw user content.">
      <section className="rounded-xl border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold text-foreground">Guardrail events</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Recent blocked and monitored activity.</p>
          </div>
          <Button variant="outline" size="sm" disabled={loading || refreshing} onClick={() => void load_events("refresh")}>
            {refreshing ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            Refresh
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 px-5 py-16 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading guardrail events...
          </div>
        ) : events.length === 0 ? (
          <div className="px-5 py-16 text-center text-sm text-muted-foreground">No guardrail events recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  {["When", "User", "Type", "Action", "Rules", "Tokens", "Prompt / response"].map((heading) => (
                    <th key={heading} className="px-5 py-3 font-medium">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((event) => {
                  const is_expanded = expanded_event_id === event.id
                  return (
                    <tr key={event.id} className="border-t border-border align-top">
                      <td className="px-5 py-4 text-muted-foreground">{format_timestamp(event.created_at)}</td>
                      <td className="px-5 py-4 text-muted-foreground">{mask_user_id(event.user_id)}</td>
                      <td className="px-5 py-4 font-medium text-foreground">{event.event_type}</td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${action_badge_class(event.action)}`}>
                          {event.action}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-muted-foreground">{event.matched_rules.join(", ") || "None"}</td>
                      <td className="px-5 py-4 text-muted-foreground">
                        {event.input_token_count === null ? "Not available" : format_count(event.input_token_count)}
                      </td>
                      <td className="min-w-72 px-5 py-4">
                        <div className="flex flex-col gap-2">
                          <div>
                            <span className="text-xs font-medium text-muted-foreground">Prompt: </span>
                            <span className="whitespace-pre-wrap break-words text-foreground">
                              {is_expanded ? event.prompt_text ?? "Not available" : truncate_text(event.prompt_text)}
                            </span>
                          </div>
                          <div>
                            <span className="text-xs font-medium text-muted-foreground">Response: </span>
                            <span className="whitespace-pre-wrap break-words text-foreground">
                              {is_expanded ? event.response_text ?? "Not available" : truncate_text(event.response_text)}
                            </span>
                          </div>
                          {event.prompt_text || event.response_text ? (
                            <button
                              type="button"
                              className="self-start text-xs font-medium text-primary hover:underline"
                              onClick={() => set_expanded_event_id((current_id) => current_id === event.id ? null : event.id)}
                            >
                              {is_expanded ? "Show less" : "Show full"}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {error ? <div className="mt-6 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}
    </DashboardShell>
  )
}
