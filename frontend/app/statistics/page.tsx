"use client"

import { UserButton } from "@clerk/nextjs"
import { ArrowLeft, Loader2, MapPin, RefreshCw, ShieldAlert, Table2 } from "lucide-react"
import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"

type IncidentStatisticResponse = {
  id: string
  company_id: string
  company_name: string
  place: string
  description: string
  type: string
  total_count: number
  updated_at: string
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
 * Formats integer counts for the statistics table.
 */
function format_count(value: number): string {
  return new Intl.NumberFormat().format(value)
}

/**
 * Formats ISO datetimes into compact local timestamps.
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
 * Returns a badge class for incident statistic categories.
 */
function type_badge_class(type: string): string {
  if (type === "Rights Violations") return "bg-rose-500/15 text-rose-700 dark:text-rose-400"
  if (type === "Displacements") return "bg-sky-500/15 text-sky-700 dark:text-sky-400"
  if (type === "Casualties") return "bg-amber-500/15 text-amber-700 dark:text-amber-400"
  if (type === "Severe Hunger") return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
  return "bg-muted text-muted-foreground"
}

export default function StatisticsPage() {
  const [rows, set_rows] = useState<IncidentStatisticResponse[]>([])
  const [loading, set_loading] = useState(true)
  const [refreshing, set_refreshing] = useState(false)
  const [error, set_error] = useState<string | null>(null)

  /**
   * Loads incident statistics from the authenticated backend proxy.
   */
  const load_rows = useCallback(async (mode: "initial" | "refresh") => {
    if (mode === "initial") {
      set_loading(true)
    } else {
      set_refreshing(true)
    }
    set_error(null)

    try {
      const response = await fetch("/api/monitoring/incident-statistics?limit=200")
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) {
        set_error(format_error_payload(data))
        return
      }
      if (!Array.isArray(data)) {
        set_error("Unexpected statistics response")
        return
      }
      set_rows(data as IncidentStatisticResponse[])
    } catch {
      set_error("Network error while loading incident statistics.")
    } finally {
      set_loading(false)
      set_refreshing(false)
    }
  }, [])

  useEffect(() => {
    void load_rows("initial")
  }, [load_rows])

  const summary = useMemo(() => {
    return rows.reduce(
      (acc, row) => {
        acc.total_reports += row.total_count
        acc.places.add(row.place)
        acc.types.add(row.type)
        return acc
      },
      { total_reports: 0, places: new Set<string>(), types: new Set<string>() },
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
            <h1 className="text-sm font-semibold text-foreground">Incident statistics</h1>
          </div>
          <Button variant="outline" size="sm" className="hidden sm:inline-flex" asChild>
            <Link href="/chat">Chat</Link>
          </Button>
          <Button variant="outline" size="sm" className="hidden sm:inline-flex" asChild>
            <Link href="/documents">Create agent</Link>
          </Button>
          <Button variant="outline" size="sm" className="hidden sm:inline-flex" asChild>
            <Link href="/dashboard">Dashboard</Link>
          </Button>
          <ThemeToggle />
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6">
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <ShieldAlert className="size-4 text-primary" />
              Total reports
            </div>
            <p className="mt-3 text-2xl font-semibold text-foreground">{format_count(summary.total_reports)}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <MapPin className="size-4 text-primary" />
              Places
            </div>
            <p className="mt-3 text-2xl font-semibold text-foreground">{format_count(summary.places.size)}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Table2 className="size-4 text-primary" />
              Categories
            </div>
            <p className="mt-3 text-2xl font-semibold text-foreground">{format_count(summary.types.size)}</p>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Regional incident counts</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Aggregated by agent, place, and incident category.
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
              Loading incident statistics...
            </div>
          ) : rows.length === 0 ? (
            <div className="px-5 py-16 text-center text-sm text-muted-foreground">
              No incident statistics have been recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-5 py-3 font-medium">Place</th>
                    <th className="px-5 py-3 font-medium">Agent</th>
                    <th className="px-5 py-3 font-medium">Description</th>
                    <th className="px-5 py-3 font-medium">Type</th>
                    <th className="px-5 py-3 font-medium">Total count</th>
                    <th className="px-5 py-3 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-t border-border align-top">
                      <td className="px-5 py-4 font-medium text-foreground">{row.place}</td>
                      <td className="px-5 py-4 text-muted-foreground">{row.company_name}</td>
                      <td className="max-w-xl px-5 py-4 text-foreground">
                        <span className="whitespace-pre-wrap break-words">{row.description}</span>
                      </td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${type_badge_class(row.type)}`}>
                          {row.type}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-medium text-foreground">{format_count(row.total_count)}</td>
                      <td className="px-5 py-4 text-muted-foreground">{format_timestamp(row.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {error ? (
            <div className="border-t border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}
        </section>
      </main>
    </div>
  )
}
