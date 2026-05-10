"use client"

import { UserButton } from "@clerk/nextjs"
import { ArrowLeft, CreditCard, Loader2, RefreshCw, ShieldAlert, Table2 } from "lucide-react"
import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"

type UserSpendResponse = {
  user_id: string
  email: string | null
  total_cost_usd: number
  total_requests: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  updated_at: string
}

type GuardrailEventResponse = {
  id: string
  user_id: string | null
  company_id: string | null
  event_type: string
  action: string
  matched_rules: string[]
  prompt_text: string | null
  response_text: string | null
  input_token_count: number | null
  created_at: string
}

/**
 * Builds a readable error string from common API payload shapes.
 */
function format_error_payload(data: unknown): string {
  if (typeof data !== "object" || data === null) return "Request failed"
  const err = (data as { error?: unknown }).error
  if (typeof err === "string") return err
  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg)
        }
        return JSON.stringify(item)
      })
      .join("; ")
  }
  return "Request failed"
}

/**
 * Formats a USD amount for compact dashboard display.
 */
function format_currency(amount: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount < 1 ? 4 : 2,
    maximumFractionDigits: amount < 1 ? 6 : 2,
  }).format(amount)
}

/**
 * Formats integers for token and request counts.
 */
function format_count(value: number): string {
  return new Intl.NumberFormat().format(value)
}

/**
 * Formats ISO datetimes into a short local timestamp.
 */
function format_timestamp(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * Masks a user identifier so the dashboard never exposes the full raw value.
 */
function mask_user_id(user_id: string | null): string {
  if (!user_id) return "Unknown user"
  const trimmed_user_id = user_id.trim()
  if (trimmed_user_id.length <= 8) return "Hidden user"
  return `${trimmed_user_id.slice(0, 4)}...${trimmed_user_id.slice(-4)}`
}

/**
 * Truncates long prompt/response text for inline table display.
 */
function truncate_text(value: string | null, max_chars = 160): string {
  if (!value) return "—"
  const trimmed_value = value.trim()
  if (trimmed_value.length <= max_chars) return trimmed_value
  return `${trimmed_value.slice(0, max_chars)}…`
}

/**
 * Returns a Tailwind colour class pair for a guardrail action badge.
 */
function action_badge_class(action: string): string {
  if (action === "blocked") return "bg-destructive/15 text-destructive"
  if (action === "monitored") return "bg-amber-500/15 text-amber-700 dark:text-amber-400"
  return "bg-muted text-muted-foreground"
}

const DashboardPage = function dashboard_page() {
  const [rows, set_rows] = useState<UserSpendResponse[]>([])
  const [loading, set_loading] = useState(true)
  const [refreshing, set_refreshing] = useState(false)
  const [error, set_error] = useState<string | null>(null)

  const [guardrail_events, set_guardrail_events] = useState<GuardrailEventResponse[]>([])
  const [guardrail_loading, set_guardrail_loading] = useState(true)
  const [guardrail_refreshing, set_guardrail_refreshing] = useState(false)
  const [guardrail_error, set_guardrail_error] = useState<string | null>(null)
  const [expanded_event_id, set_expanded_event_id] = useState<string | null>(null)

  /**
   * Loads the usage dashboard rows from the authenticated backend proxy.
   */
  const load_rows = useCallback(async (mode: "initial" | "refresh") => {
    if (mode === "initial") {
      set_loading(true)
    } else {
      set_refreshing(true)
    }
    set_error(null)

    try {
      const response = await fetch("/api/usage")
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) {
        set_error(format_error_payload(data))
        return
      }
      if (!Array.isArray(data)) {
        set_error("Unexpected usage response")
        return
      }
      set_rows(data as UserSpendResponse[])
    } catch {
      set_error("Network error while loading spend data.")
    } finally {
      set_loading(false)
      set_refreshing(false)
    }
  }, [])

  /**
   * Loads recent guardrail audit rows from the authenticated backend proxy.
   */
  const load_guardrail_events = useCallback(async (mode: "initial" | "refresh") => {
    if (mode === "initial") {
      set_guardrail_loading(true)
    } else {
      set_guardrail_refreshing(true)
    }
    set_guardrail_error(null)

    try {
      const response = await fetch("/api/monitoring/guardrail-events?limit=50")
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) {
        set_guardrail_error(format_error_payload(data))
        return
      }
      if (!Array.isArray(data)) {
        set_guardrail_error("Unexpected guardrail events response")
        return
      }
      set_guardrail_events(data as GuardrailEventResponse[])
    } catch {
      set_guardrail_error("Network error while loading guardrail events.")
    } finally {
      set_guardrail_loading(false)
      set_guardrail_refreshing(false)
    }
  }, [])

  useEffect(() => {
    void load_rows("initial")
    void load_guardrail_events("initial")
  }, [load_rows, load_guardrail_events])

  const summary = useMemo(() => {
    return rows.reduce(
      (acc, row) => {
        acc.total_cost_usd += row.total_cost_usd
        acc.total_requests += row.total_requests
        acc.total_tokens += row.total_tokens
        return acc
      },
      { total_cost_usd: 0, total_requests: 0, total_tokens: 0 },
    )
  }, [rows])

  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/90 px-4 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3">
          <Button variant="ghost" size="icon-sm" asChild>
            <Link href="/" aria-label="Back to home">
              <ArrowLeft />
            </Link>
          </Button>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm font-semibold text-foreground">Usage dashboard</h1>
          </div>
          <Button variant="outline" size="sm" className="hidden sm:inline-flex" asChild>
            <Link href="/chat">Chat</Link>
          </Button>
          <Button variant="outline" size="sm" className="hidden sm:inline-flex" asChild>
            <Link href="/documents">Create agent</Link>
          </Button>
          <ThemeToggle />
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6">
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <CreditCard className="size-4 text-primary" />
              Total spend
            </div>
            <p className="mt-3 text-2xl font-semibold text-foreground">{format_currency(summary.total_cost_usd)}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Table2 className="size-4 text-primary" />
              Tracked users
            </div>
            <p className="mt-3 text-2xl font-semibold text-foreground">{format_count(rows.length)}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <RefreshCw className="size-4 text-primary" />
              Total requests
            </div>
            <p className="mt-3 text-2xl font-semibold text-foreground">{format_count(summary.total_requests)}</p>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
            <div>
              <h2 className="text-sm font-semibold text-foreground">User spend</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Per-user cumulative spend and token totals from model usage.
              </p>
            </div>
            <Button variant="outline" size="sm" disabled={loading || refreshing} onClick={() => void load_rows("refresh")}>
              {refreshing ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              Refresh
            </Button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center gap-2 px-5 py-16 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading dashboard…
            </div>
          ) : rows.length === 0 ? (
            <div className="px-5 py-16 text-center text-sm text-muted-foreground">
              No spend has been recorded yet. Once users chat or trigger embeddings, rows will appear here.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-5 py-3 font-medium">User</th>
                    <th className="px-5 py-3 font-medium">Cost</th>
                    <th className="px-5 py-3 font-medium">Requests</th>
                    <th className="px-5 py-3 font-medium">Prompt tokens</th>
                    <th className="px-5 py-3 font-medium">Completion tokens</th>
                    <th className="px-5 py-3 font-medium">Total tokens</th>
                    <th className="px-5 py-3 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.user_id} className="border-t border-border align-top">
                      <td className="px-5 py-4">
                        <div className="font-medium text-foreground">
                          {row.email ?? mask_user_id(row.user_id)}
                        </div>
                      </td>
                      <td className="px-5 py-4 font-medium text-foreground">{format_currency(row.total_cost_usd)}</td>
                      <td className="px-5 py-4 text-muted-foreground">{format_count(row.total_requests)}</td>
                      <td className="px-5 py-4 text-muted-foreground">{format_count(row.total_prompt_tokens)}</td>
                      <td className="px-5 py-4 text-muted-foreground">{format_count(row.total_completion_tokens)}</td>
                      <td className="px-5 py-4 text-muted-foreground">{format_count(row.total_tokens)}</td>
                      <td className="px-5 py-4 text-muted-foreground">{format_timestamp(row.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <ShieldAlert className="size-4 text-primary" />
                Guardrail events
              </h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Prompts blocked for size and replies flagged for personal information (email or phone).
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={guardrail_loading || guardrail_refreshing}
              onClick={() => void load_guardrail_events("refresh")}
            >
              {guardrail_refreshing ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              Refresh
            </Button>
          </div>

          {guardrail_loading ? (
            <div className="flex items-center justify-center gap-2 px-5 py-16 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading guardrail events…
            </div>
          ) : guardrail_events.length === 0 ? (
            <div className="px-5 py-16 text-center text-sm text-muted-foreground">
              No guardrail events recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-5 py-3 font-medium">When</th>
                    <th className="px-5 py-3 font-medium">User</th>
                    <th className="px-5 py-3 font-medium">Type</th>
                    <th className="px-5 py-3 font-medium">Action</th>
                    <th className="px-5 py-3 font-medium">Rules</th>
                    <th className="px-5 py-3 font-medium">Tokens</th>
                    <th className="px-5 py-3 font-medium">Prompt / response</th>
                  </tr>
                </thead>
                <tbody>
                  {guardrail_events.map((event) => {
                    const is_expanded = expanded_event_id === event.id
                    return (
                      <tr key={event.id} className="border-t border-border align-top">
                        <td className="px-5 py-4 text-muted-foreground">{format_timestamp(event.created_at)}</td>
                        <td className="px-5 py-4 text-muted-foreground">{mask_user_id(event.user_id)}</td>
                        <td className="px-5 py-4 font-medium text-foreground">{event.event_type}</td>
                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${action_badge_class(
                              event.action,
                            )}`}
                          >
                            {event.action}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-muted-foreground">
                          {event.matched_rules.length > 0 ? event.matched_rules.join(", ") : "—"}
                        </td>
                        <td className="px-5 py-4 text-muted-foreground">
                          {event.input_token_count !== null ? format_count(event.input_token_count) : "—"}
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex flex-col gap-1">
                            <div>
                              <span className="text-xs font-medium text-muted-foreground">Prompt: </span>
                              <span className="whitespace-pre-wrap break-words text-foreground">
                                {is_expanded ? event.prompt_text ?? "—" : truncate_text(event.prompt_text)}
                              </span>
                            </div>
                            <div>
                              <span className="text-xs font-medium text-muted-foreground">Response: </span>
                              <span className="whitespace-pre-wrap break-words text-foreground">
                                {is_expanded ? event.response_text ?? "—" : truncate_text(event.response_text)}
                              </span>
                            </div>
                            {(event.prompt_text || event.response_text) ? (
                              <button
                                type="button"
                                className="self-start text-xs font-medium text-primary hover:underline"
                                onClick={() =>
                                  set_expanded_event_id((prev) => (prev === event.id ? null : event.id))
                                }
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

          {guardrail_error ? (
            <div className="border-t border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive">
              {guardrail_error}
            </div>
          ) : null}
        </section>

        {error ? (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}
      </main>
    </div>
  )
}

export default DashboardPage
