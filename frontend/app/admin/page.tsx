"use client"

import { useEffect, useMemo, useState } from "react"

import { DashboardShell } from "@/components/dashboard-shell"
import { Button } from "@/components/ui/button"

type Agent = {
  id: string
  name: string
  email: string
  owner_id: string
  is_approved: boolean
  created_at: string
}

const PAGE_SIZE = 10

function error_text(data: unknown): string {
  if (typeof data === "object" && data !== null && "detail" in data)
    return String((data as { detail: unknown }).detail)
  return "The agent dashboard is temporarily unavailable. Please try again."
}

export default function AdminAgentsPage() {
  const [agents, set_agents] = useState<Agent[]>([])
  const [search, set_search] = useState("")
  const [page, set_page] = useState(1)
  const [error, set_error] = useState<string | null>(null)
  const [busy, set_busy] = useState<string | null>(null)

  const load = async () => {
    const response = await fetch("/api/admin/agents", { cache: "no-store" })
    const data: unknown = await response.json().catch(() => ({}))
    if (!response.ok) {
      set_error(error_text(data))
      return
    }
    if (Array.isArray(data)) set_agents(data as Agent[])
  }

  useEffect(() => {
    void Promise.resolve().then(load)
  }, [])

  const filtered_agents = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    if (!query) return agents
    return agents.filter(
      (agent) =>
        agent.name.toLocaleLowerCase().includes(query) ||
        agent.email.toLocaleLowerCase().includes(query)
    )
  }, [agents, search])
  const page_count = Math.max(1, Math.ceil(filtered_agents.length / PAGE_SIZE))
  const current_page = Math.min(page, page_count)
  const visible_agents = filtered_agents.slice(
    (current_page - 1) * PAGE_SIZE,
    current_page * PAGE_SIZE
  )

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

  return (
    <DashboardShell
      title="Agent approvals"
      description="Only approved agents are available through web chat and WhatsApp."
    >
      <div className="overflow-hidden rounded-xl border border-[#dce4ef] bg-white shadow-sm">
        {error ? (
          <p
            role="alert"
            className="m-4 rounded-lg bg-red-50 p-3 text-sm text-[#DC2626]"
          >
            {error}
          </p>
        ) : null}
        <div className="border-b border-[#dce4ef] p-4">
          <label className="block max-w-md text-sm font-medium text-[#1E3A8A]">
            Search agents
            <input
              type="search"
              value={search}
              onChange={(event) => {
                set_search(event.target.value)
                set_page(1)
              }}
              placeholder="Search by name or email"
              className="mt-1 w-full rounded-lg border border-[#b9cdeb] px-3 py-2 text-foreground outline-none focus:ring-2 focus:ring-[#60A5FA]"
            />
          </label>
        </div>
        <div className="overflow-x-auto">
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
              {visible_agents.map((agent) => (
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
                    <Button
                      type="button"
                      disabled={busy === agent.id}
                      onClick={() => void change_status(agent)}
                      className={
                        agent.is_approved
                          ? "bg-[#DC2626] text-white hover:bg-red-700"
                          : "bg-[#2563EB] text-white hover:bg-[#1E3A8A]"
                      }
                    >
                      {busy === agent.id
                        ? "Saving…"
                        : agent.is_approved
                          ? "Suspend"
                          : "Approve"}
                    </Button>
                  </td>
                </tr>
              ))}
              {visible_agents.length === 0 ? (
                <tr>
                  <td colSpan={4} className="p-8 text-center text-slate-500">
                    {search ? "No agents match that name or email." : "No agents found."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col gap-3 border-t border-[#dce4ef] px-4 py-3 text-sm text-[#607694] sm:flex-row sm:items-center sm:justify-between">
          <span>
            {filtered_agents.length === 0
              ? "0 agents"
              : `${(current_page - 1) * PAGE_SIZE + 1}–${Math.min(current_page * PAGE_SIZE, filtered_agents.length)} of ${filtered_agents.length} agents`}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={current_page === 1}
              onClick={() => set_page((current) => current - 1)}
            >
              Previous
            </Button>
            <span>
              Page {current_page} of {page_count}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={current_page === page_count}
              onClick={() => set_page((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </DashboardShell>
  )
}
