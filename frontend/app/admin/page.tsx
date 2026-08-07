"use client"

import { useEffect, useState } from "react"
import { DashboardShell } from "@/components/dashboard-shell"

type Agent = { id: string; name: string; email: string; owner_id: string; is_approved: boolean; created_at: string }

function error_text(data: unknown): string {
  if (typeof data === "object" && data !== null && "detail" in data) return String((data as { detail: unknown }).detail)
  return "The agent dashboard is temporarily unavailable. Please try again."
}

export default function AdminAgentsPage() {
  const [agents, set_agents] = useState<Agent[]>([])
  const [error, set_error] = useState<string | null>(null)
  const [busy, set_busy] = useState<string | null>(null)
  const load = async () => {
    const response = await fetch("/api/admin/agents", { cache: "no-store" })
    const data: unknown = await response.json().catch(() => ({}))
    if (!response.ok) { set_error(error_text(data)); return }
    if (Array.isArray(data)) set_agents(data as Agent[])
  }
  useEffect(() => { void Promise.resolve().then(load) }, [])
  const change_status = async (agent: Agent) => {
    set_busy(agent.id); set_error(null)
    try {
      const response = await fetch(`/api/admin/agents/${encodeURIComponent(agent.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approved: !agent.is_approved }) })
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) { set_error(error_text(data)); return }
      set_agents((current) => current.map((item) => item.id === agent.id ? data as Agent : item))
    } catch { set_error("The agent status could not be changed. Please check your connection and try again.") }
    finally { set_busy(null) }
  }
  return <DashboardShell title="Agent approvals" description="Only approved agents are available through web chat and WhatsApp."><div className="overflow-x-auto rounded-xl border border-[#dce4ef] bg-white shadow-sm">{error ? <p role="alert" className="m-4 rounded-lg bg-red-50 p-3 text-sm text-[#DC2626]">{error}</p> : null}<table className="w-full min-w-[680px] text-left text-sm"><thead className="bg-[#1E3A8A] text-white"><tr><th className="p-4">Agent</th><th className="p-4">Owner</th><th className="p-4">Status</th><th className="p-4">Action</th></tr></thead><tbody>{agents.map((agent) => <tr key={agent.id} className="border-t"><td className="p-4"><div className="font-medium">{agent.name}</div><div className="text-slate-500">{agent.email}</div></td><td className="p-4 text-slate-600">{agent.owner_id}</td><td className="p-4"><span className={agent.is_approved ? "text-green-700" : "text-amber-700"}>{agent.is_approved ? "Approved" : "Not approved"}</span></td><td className="p-4"><button type="button" disabled={busy === agent.id} onClick={() => void change_status(agent)} className={agent.is_approved ? "rounded-md bg-[#DC2626] px-3 py-2 text-white disabled:opacity-50" : "rounded-md bg-[#2563EB] px-3 py-2 text-white disabled:opacity-50"}>{busy === agent.id ? "Saving…" : agent.is_approved ? "Suspend" : "Approve"}</button></td></tr>)}{agents.length === 0 ? <tr><td colSpan={4} className="p-8 text-center text-slate-500">No agents found.</td></tr> : null}</tbody></table></div></DashboardShell>
}
