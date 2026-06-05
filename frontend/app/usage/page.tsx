"use client"

import { CreditCard, Loader2, RefreshCw, Table2 } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { DashboardShell } from "@/components/dashboard-shell"
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

// Builds a readable error string from common API payload shapes.
function format_error_payload(data: unknown): string {
  if (typeof data !== "object" || data === null) return "Request failed"
  const error = (data as { error?: unknown }).error
  if (typeof error === "string") return error
  const detail = (data as { detail?: unknown }).detail
  return typeof detail === "string" ? detail : "Request failed"
}

// Formats a USD amount for compact display.
function format_currency(amount: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount < 1 ? 4 : 2,
    maximumFractionDigits: amount < 1 ? 6 : 2,
  }).format(amount)
}

// Formats integer counts.
function format_count(value: number): string {
  return new Intl.NumberFormat().format(value)
}

// Formats ISO datetimes into a short local timestamp.
function format_timestamp(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
}

// Masks a user identifier so the page never exposes the full raw value.
function mask_user_id(user_id: string): string {
  const trimmed_user_id = user_id.trim()
  return trimmed_user_id.length <= 8 ? "Hidden user" : `${trimmed_user_id.slice(0, 4)}...${trimmed_user_id.slice(-4)}`
}

export default function UsagePage() {
  const [rows, set_rows] = useState<UserSpendResponse[]>([])
  const [loading, set_loading] = useState(true)
  const [refreshing, set_refreshing] = useState(false)
  const [error, set_error] = useState<string | null>(null)

  /**
   * Loads cumulative usage rows from the authenticated backend proxy.
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
      if (!response.ok) return set_error(format_error_payload(data))
      if (!Array.isArray(data)) return set_error("Unexpected usage response")
      set_rows(data as UserSpendResponse[])
    } catch {
      set_error("Network error while loading spend data.")
    } finally {
      set_loading(false)
      set_refreshing(false)
    }
  }, [])

  useEffect(() => {
    const timeout_id = window.setTimeout(() => void load_rows("initial"), 0)
    return () => window.clearTimeout(timeout_id)
  }, [load_rows])

  const summary = useMemo(
    () =>
      rows.reduce(
        (acc, row) => ({
          total_cost_usd: acc.total_cost_usd + row.total_cost_usd,
          total_requests: acc.total_requests + row.total_requests,
        }),
        { total_cost_usd: 0, total_requests: 0 },
      ),
    [rows],
  )

  return (
    <DashboardShell title="Usage" description="Monitor model spend and request volume.">
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { label: "Total spend", value: format_currency(summary.total_cost_usd), icon: CreditCard },
          { label: "Tracked users", value: format_count(rows.length), icon: Table2 },
          { label: "Total requests", value: format_count(summary.total_requests), icon: RefreshCw },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <item.icon className="size-4 text-primary" />
              {item.label}
            </div>
            <p className="mt-3 text-2xl font-semibold text-foreground">{item.value}</p>
          </div>
        ))}
      </section>

      <section className="mt-6 rounded-xl border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold text-foreground">User spend</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Cumulative spend and token totals by user.</p>
          </div>
          <Button variant="outline" size="sm" disabled={loading || refreshing} onClick={() => void load_rows("refresh")}>
            {refreshing ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            Refresh
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 px-5 py-16 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading usage...
          </div>
        ) : rows.length === 0 ? (
          <div className="px-5 py-16 text-center text-sm text-muted-foreground">No spend has been recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  {["User", "Cost", "Requests", "Prompt tokens", "Completion tokens", "Total tokens", "Updated"].map(
                    (heading) => (
                      <th key={heading} className="px-5 py-3 font-medium">{heading}</th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.user_id} className="border-t border-border">
                    <td className="px-5 py-4 font-medium text-foreground">{row.email ?? mask_user_id(row.user_id)}</td>
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

      {error ? <div className="mt-6 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}
    </DashboardShell>
  )
}
