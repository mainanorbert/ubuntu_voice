"use client"

import Link from "next/link"
import {
  Loader2,
  MapPin,
  Pencil,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from "lucide-react"
import { FormEvent, useCallback, useEffect, useState } from "react"

import { DashboardShell } from "@/components/dashboard-shell"
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
type Agent = { id: string; name: string }
type StatisticsSummary = {
  total_reports: number
  places: number
  categories: number
}
type StatisticsPage = {
  items: IncidentStatisticResponse[]
  total: number
  page: number
  page_size: number
  summary: StatisticsSummary
  agents: Agent[]
}

const INCIDENT_TYPES = [
  "Rights Violations",
  "Displacements",
  "Casualties",
  "Severe Hunger",
] as const

type EditForm = {
  place: string
  description: string
  type: (typeof INCIDENT_TYPES)[number]
  total_count: string
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
  if (type === "Rights Violations")
    return "bg-rose-500/15 text-rose-700 dark:text-rose-400"
  if (type === "Displacements")
    return "bg-sky-500/15 text-sky-700 dark:text-sky-400"
  if (type === "Casualties")
    return "bg-amber-500/15 text-amber-700 dark:text-amber-400"
  if (type === "Severe Hunger")
    return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
  return "bg-muted text-muted-foreground"
}

export default function StatisticsPage() {
  const [rows, set_rows] = useState<IncidentStatisticResponse[]>([])
  const [loading, set_loading] = useState(true)
  const [refreshing, set_refreshing] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const [notice, set_notice] = useState<string | null>(null)
  const [agent_id, set_agent_id] = useState("")
  const [agents, set_agents] = useState<Agent[]>([])
  const [page, set_page] = useState(1)
  const [total, set_total] = useState(0)
  const [summary, set_summary] = useState<StatisticsSummary>({
    total_reports: 0,
    places: 0,
    categories: 0,
  })
  const [editing_row, set_editing_row] =
    useState<IncidentStatisticResponse | null>(null)
  const [edit_form, set_edit_form] = useState<EditForm | null>(null)
  const [saving, set_saving] = useState(false)
  const [deleting_id, set_deleting_id] = useState<string | null>(null)
  const page_size = 25

  /**
   * Loads incident statistics from the authenticated backend proxy.
   */
  const load_rows = useCallback(
    async (
      mode: "initial" | "refresh",
      requested_page = page,
      requested_agent_id = agent_id
    ) => {
      if (mode === "initial") {
        set_loading(true)
      } else {
        set_refreshing(true)
      }
      set_error(null)

      try {
        const search = new URLSearchParams({
          page: String(requested_page),
          page_size: String(page_size),
        })
        if (requested_agent_id) search.set("agent_id", requested_agent_id)
        const response = await fetch(
          `/api/monitoring/incident-statistics?${search}`
        )
        const data: unknown = await response.json().catch(() => ({}))
        if (!response.ok) {
          set_error(format_error_payload(data))
          return
        }
        if (!is_statistics_page(data)) {
          set_error("Unexpected statistics response")
          return
        }
        set_rows(data.items)
        set_total(data.total)
        set_page(data.page)
        set_summary(data.summary)
        set_agents(data.agents)
      } catch {
        set_error("Network error while loading incident statistics.")
      } finally {
        set_loading(false)
        set_refreshing(false)
      }
    },
    [agent_id, page]
  )

  useEffect(() => {
    const initial_load = window.setTimeout(() => void load_rows("initial"), 0)
    return () => window.clearTimeout(initial_load)
  }, [load_rows])

  const total_pages = Math.max(1, Math.ceil(total / page_size))

  function begin_edit(row: IncidentStatisticResponse) {
    set_error(null)
    set_notice(null)
    set_editing_row(row)
    set_edit_form({
      place: row.place,
      description: row.description,
      type: row.type as EditForm["type"],
      total_count: String(row.total_count),
    })
  }

  function cancel_edit() {
    set_editing_row(null)
    set_edit_form(null)
  }

  async function save_edit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editing_row || !edit_form) return
    set_saving(true)
    set_error(null)
    set_notice(null)
    try {
      const response = await fetch(
        `/api/monitoring/incident-statistics/${editing_row.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...edit_form,
            total_count: Number(edit_form.total_count),
          }),
        }
      )
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) {
        set_error(format_error_payload(data))
        return
      }
      cancel_edit()
      set_notice("Statistic updated.")
      await load_rows("refresh")
    } catch {
      set_error("Network error while saving the statistic. Please try again.")
    } finally {
      set_saving(false)
    }
  }

  async function delete_row(row: IncidentStatisticResponse) {
    if (
      !window.confirm(
        `Delete the ${row.type.toLowerCase()} statistic for ${row.place}? This cannot be undone.`
      )
    )
      return
    set_deleting_id(row.id)
    set_error(null)
    set_notice(null)
    try {
      const response = await fetch(
        `/api/monitoring/incident-statistics/${row.id}`,
        { method: "DELETE" }
      )
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) {
        set_error(format_error_payload(data))
        return
      }
      if (editing_row?.id === row.id) cancel_edit()
      set_notice("Statistic deleted.")
      await load_rows(
        "refresh",
        rows.length === 1 && page > 1 ? page - 1 : page
      )
    } catch {
      set_error("Network error while deleting the statistic. Please try again.")
    } finally {
      set_deleting_id(null)
    }
  }

  return (
    <DashboardShell
      title="Incident statistics"
      description="Monitor reported incidents by agent, location, and category."
    >
      <div className="flex flex-col gap-6">
        <div>
          <Link
            href="/places"
            className="inline-flex items-center gap-2 rounded-lg bg-[#2563EB] px-3 py-2 text-sm font-medium text-white hover:bg-[#1E3A8A] focus-visible:ring-2 focus-visible:ring-[#60A5FA] focus-visible:outline-none"
          >
            {" "}
            <MapPin className="size-4" /> Manage known places
          </Link>
        </div>
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-[#dce4ef] bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-[#607694]">
              <ShieldAlert className="size-4 text-[#2864e8]" />
              Total reports
            </div>
            <p className="mt-3 text-2xl font-semibold text-[#061b3b]">
              {format_count(summary.total_reports)}
            </p>
          </div>
          <div className="rounded-xl border border-[#dce4ef] bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-[#607694]">
              <MapPin className="size-4 text-[#2864e8]" />
              Places
            </div>
            <p className="mt-3 text-2xl font-semibold text-[#061b3b]">
              {format_count(summary.places)}
            </p>
          </div>
          <div className="rounded-xl border border-[#dce4ef] bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-medium text-[#607694]">
              <ShieldAlert className="size-4 text-[#2864e8]" />
              Total reported cases
            </div>
            <p className="mt-3 text-2xl font-semibold text-[#061b3b]">
              {format_count(summary.total_reports)}
            </p>
          </div>
        </section>

        <section className="rounded-xl border border-[#dce4ef] bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-[#dce4ef] px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                Regional incident counts
              </h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Aggregated by agent, place, and incident category.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-sm text-[#607694]">
                Agent{" "}
                <select
                  value={agent_id}
                  onChange={(event) => {
                    const next_agent_id = event.target.value
                    set_agent_id(next_agent_id)
                    set_page(1)
                    void load_rows("refresh", 1, next_agent_id)
                  }}
                  className="ml-1 rounded-lg border border-[#b9cdeb] bg-white px-2 py-1.5 text-[#1E3A8A] outline-none focus:ring-2 focus:ring-[#60A5FA]"
                >
                  <option value="">All agents</option>
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                variant="outline"
                size="sm"
                className="border-[#b9cdeb] text-[#123f88] hover:bg-[#eef5ff]"
                disabled={loading || refreshing}
                onClick={() => void load_rows("refresh")}
              >
                {refreshing ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <RefreshCw className="size-4" />
                )}
                Refresh
              </Button>
            </div>
          </div>

          {editing_row && edit_form ? (
            <form
              onSubmit={save_edit}
              className="border-b border-[#dce4ef] bg-[#F8FAFC] px-5 py-5"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
                <label className="min-w-0 flex-1 text-sm font-medium text-[#1E3A8A]">
                  Place <span className="text-[#DC2626]">*</span>
                  <input
                    required
                    maxLength={160}
                    value={edit_form.place}
                    onChange={(event) =>
                      set_edit_form({ ...edit_form, place: event.target.value })
                    }
                    className="mt-1 w-full rounded-lg border border-[#b9cdeb] bg-white px-3 py-2 text-foreground outline-none focus:ring-2 focus:ring-[#60A5FA]"
                  />
                </label>
                <label className="min-w-0 flex-[2] text-sm font-medium text-[#1E3A8A]">
                  Description <span className="text-[#DC2626]">*</span>
                  <input
                    required
                    maxLength={500}
                    value={edit_form.description}
                    onChange={(event) =>
                      set_edit_form({
                        ...edit_form,
                        description: event.target.value,
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-[#b9cdeb] bg-white px-3 py-2 text-foreground outline-none focus:ring-2 focus:ring-[#60A5FA]"
                  />
                </label>
                <label className="text-sm font-medium text-[#1E3A8A]">
                  Type <span className="text-[#DC2626]">*</span>
                  <select
                    value={edit_form.type}
                    onChange={(event) =>
                      set_edit_form({
                        ...edit_form,
                        type: event.target.value as EditForm["type"],
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-[#b9cdeb] bg-white px-3 py-2 text-foreground outline-none focus:ring-2 focus:ring-[#60A5FA]"
                  >
                    {INCIDENT_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium text-[#1E3A8A]">
                  Total count <span className="text-[#DC2626]">*</span>
                  <input
                    required
                    type="number"
                    min="1"
                    max="1000000000"
                    value={edit_form.total_count}
                    onChange={(event) =>
                      set_edit_form({
                        ...edit_form,
                        total_count: event.target.value,
                      })
                    }
                    className="mt-1 w-32 rounded-lg border border-[#b9cdeb] bg-white px-3 py-2 text-foreground outline-none focus:ring-2 focus:ring-[#60A5FA]"
                  />
                </label>
                <div className="flex gap-2">
                  <Button type="submit" disabled={saving}>
                    {saving ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : null}
                    Save
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={saving}
                    onClick={cancel_edit}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </form>
          ) : null}

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
                <thead className="bg-[#eef5ff] text-xs tracking-wide text-[#607694] uppercase">
                  <tr>
                    <th className="px-5 py-3 font-medium">Place</th>
                    <th className="px-5 py-3 font-medium">Agent</th>
                    <th className="px-5 py-3 font-medium">Description</th>
                    <th className="px-5 py-3 font-medium">Type</th>
                    <th className="px-5 py-3 font-medium">Total count</th>
                    <th className="px-5 py-3 font-medium">Updated</th>
                    <th className="px-5 py-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-t border-[#edf1f6] align-top"
                    >
                      <td className="px-5 py-4 font-medium text-foreground">
                        {row.place}
                      </td>
                      <td className="px-5 py-4 text-muted-foreground">
                        {row.company_name}
                      </td>
                      <td className="max-w-xl px-5 py-4 text-foreground">
                        <span className="break-words whitespace-pre-wrap">
                          {row.description}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${type_badge_class(row.type)}`}
                        >
                          {row.type}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-medium text-foreground">
                        {format_count(row.total_count)}
                      </td>
                      <td className="px-5 py-4 text-muted-foreground">
                        {format_timestamp(row.updated_at)}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={saving || deleting_id === row.id}
                            onClick={() => begin_edit(row)}
                            aria-label={`Edit statistic for ${row.place}`}
                          >
                            <Pencil className="size-3" /> Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            disabled={saving || deleting_id === row.id}
                            onClick={() => void delete_row(row)}
                            aria-label={`Delete statistic for ${row.place}`}
                          >
                            {deleting_id === row.id ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <Trash2 className="size-3" />
                            )}{" "}
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > 0 ? (
            <div className="flex items-center justify-between gap-3 border-t border-[#dce4ef] px-5 py-3 text-sm text-[#607694]">
              <span>
                Page {page} of {total_pages} · {format_count(total)} records
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={loading || refreshing || page <= 1}
                  onClick={() => void load_rows("refresh", page - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={loading || refreshing || page >= total_pages}
                  onClick={() => void load_rows("refresh", page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}

          {error ? (
            <div className="border-t border-destructive/40 bg-destructive/10 px-5 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}
          {notice ? (
            <div
              className="border-t border-[#60A5FA] bg-[#eff6ff] px-5 py-3 text-sm text-[#1E3A8A]"
              role="status"
            >
              {notice}
            </div>
          ) : null}
        </section>
      </div>
    </DashboardShell>
  )
}

function is_statistics_page(value: unknown): value is StatisticsPage {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as StatisticsPage).items) &&
    typeof (value as StatisticsPage).total === "number" &&
    Array.isArray((value as StatisticsPage).agents)
  )
}
