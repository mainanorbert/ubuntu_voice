"use client"

import { useCallback, useEffect, useState } from "react"
import { DashboardShell } from "@/components/dashboard-shell"

type Agent = {
  id: string
  name: string
  email: string
  owner_id: string
  is_approved: boolean
  created_at: string
}
type AgentPage = {
  agents: Agent[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

const page_size = 20

function error_text(data: unknown): string {
  if (typeof data === "object" && data !== null && "detail" in data)
    return String((data as { detail: unknown }).detail)
  return "The agent dashboard is temporarily unavailable. Please try again."
}

export default function AdminAgentsPage() {
  const [agents, set_agents] = useState<Agent[]>([])
  const [page, set_page] = useState(1)
  const [total, set_total] = useState(0)
  const [total_pages, set_total_pages] = useState(0)
  const [search_input, set_search_input] = useState("")
  const [search, set_search] = useState("")
  const [error, set_error] = useState<string | null>(null)
  const [busy, set_busy] = useState<string | null>(null)
  const [loading, set_loading] = useState(true)

  const load = useCallback(
    async (
      requested_page: number,
      requested_search: string,
      signal?: AbortSignal
    ) => {
      set_loading(true)
      try {
        const params = new URLSearchParams({
          page: String(requested_page),
          page_size: String(page_size),
        })
        if (requested_search) params.set("search", requested_search)
        const response = await fetch(`/api/admin/agents?${params.toString()}`, {
          cache: "no-store",
          signal,
        })
        const data: unknown = await response.json().catch(() => ({}))
        if (!response.ok) {
          set_error(error_text(data))
          return
        }
        const result = data as Partial<AgentPage>
        if (
          !Array.isArray(result.agents) ||
          typeof result.total !== "number" ||
          typeof result.total_pages !== "number"
        ) {
          set_error(
            "The agent dashboard returned an unexpected response. Please try again."
          )
          return
        }
        set_agents(result.agents as Agent[])
        set_total(result.total)
        set_total_pages(result.total_pages)
        set_error(null)
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError")
          return
        set_error(
          "The agent dashboard is temporarily unavailable. Please check your connection and try again."
        )
      } finally {
        if (!signal?.aborted) set_loading(false)
      }
    },
    []
  )

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      set_page(1)
      set_search(search_input.trim())
    }, 300)
    return () => window.clearTimeout(timeout)
  }, [search_input])

  useEffect(() => {
    const controller = new AbortController()
    void Promise.resolve().then(() => load(page, search, controller.signal))
    return () => controller.abort()
  }, [load, page, search])
  const change_status = async (agent: Agent) => {
    set_busy(agent.id)
    set_error(null)
    try {
      const response = await fetch(
        `/api/admin/agents/${encodeURIComponent(agent.id)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved: !agent.is_approved }),
        }
      )
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) {
        set_error(error_text(data))
        return
      }
      set_agents((current) =>
        current.map((item) => (item.id === agent.id ? (data as Agent) : item))
      )
    } catch {
      set_error(
        "The agent status could not be changed. Please check your connection and try again."
      )
    } finally {
      set_busy(null)
    }
  }
  const first_item = total === 0 ? 0 : (page - 1) * page_size + 1
  const last_item = Math.min(page * page_size, total)
  return (
    <DashboardShell
      title="Agent approvals"
      description="Only approved agents are available through web chat and WhatsApp."
    >
      <div className="space-y-4">
        <div>
          <label
            htmlFor="agent-search"
            className="mb-1 block text-sm font-medium text-[#1E3A8A]"
          >
            Search agents
          </label>
          <input
            id="agent-search"
            type="search"
            value={search_input}
            onChange={(event) => set_search_input(event.target.value)}
            placeholder="Search by name or email"
            className="w-full rounded-lg border border-[#94a3b8] bg-white px-3 py-2 text-sm outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#60A5FA] sm:max-w-md"
          />
        </div>
        <div className="overflow-x-auto rounded-xl border border-[#dce4ef] bg-white shadow-sm">
          {error ? (
            <p
              role="alert"
              className="m-4 rounded-lg bg-red-50 p-3 text-sm text-[#DC2626]"
            >
              {error}
            </p>
          ) : null}
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="bg-[#1E3A8A] text-white">
              <tr>
                <th className="p-4">Agent</th>
                <th className="p-4">Owner</th>
                <th className="p-4">Status</th>
                <th className="p-4">Action</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id} className="border-t">
                  <td className="p-4">
                    <div className="font-medium">{agent.name}</div>
                    <div className="text-slate-500">{agent.email}</div>
                  </td>
                  <td className="p-4 text-slate-600">{agent.owner_id}</td>
                  <td className="p-4">
                    <span
                      className={
                        agent.is_approved ? "text-green-700" : "text-amber-700"
                      }
                    >
                      {agent.is_approved ? "Approved" : "Not approved"}
                    </span>
                  </td>
                  <td className="p-4">
                    <button
                      type="button"
                      disabled={busy === agent.id}
                      onClick={() => void change_status(agent)}
                      className={
                        agent.is_approved
                          ? "rounded-md bg-[#DC2626] px-3 py-2 text-white disabled:opacity-50"
                          : "rounded-md bg-[#2563EB] px-3 py-2 text-white disabled:opacity-50"
                      }
                    >
                      {busy === agent.id
                        ? "Saving…"
                        : agent.is_approved
                          ? "Suspend"
                          : "Approve"}
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && agents.length === 0 ? (
                <tr>
                  <td colSpan={4} className="p-8 text-center text-slate-500">
                    No agents match your search.
                  </td>
                </tr>
              ) : null}
              {loading ? (
                <tr>
                  <td colSpan={4} className="p-8 text-center text-slate-500">
                    Loading agents…
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        {total_pages > 0 ? (
          <div className="flex flex-col gap-3 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between">
            <p>
              Showing {first_item}–{last_item} of {total} agents
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => set_page((current) => current - 1)}
                disabled={page === 1 || loading}
                className="rounded-md border border-[#2563EB] px-3 py-2 text-[#1E3A8A] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Previous
              </button>
              <span aria-live="polite">
                Page {page} of {total_pages}
              </span>
              <button
                type="button"
                onClick={() => set_page((current) => current + 1)}
                disabled={page >= total_pages || loading}
                className="rounded-md bg-[#2563EB] px-3 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </DashboardShell>
  )
}
