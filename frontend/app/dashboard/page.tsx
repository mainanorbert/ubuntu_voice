"use client"

import Link from "next/link"
import Image from "next/image"
import { useEffect, useState } from "react"
import type { ReactNode } from "react"
import { BarChart3, Gauge, Home, ShieldAlert } from "lucide-react"
import { ProfileMenu } from "@/components/profile-menu"

type CurrentUser = { name: string | null }

/** Renders the calm, low-bandwidth community safety dashboard overview. */
export default function DashboardPage() {
  const [user, set_user] = useState<CurrentUser | null>(null)

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((profile: CurrentUser | null) => set_user(profile))
      .catch(() => set_user(null))
  }, [])

  const name = user?.name || "Ubuntu Voice user"

  return (
    <div className="min-h-svh bg-[#f7f9fc] text-[#061b3b]">
      <header className="flex h-[91px] items-center justify-between bg-[#23418d] px-6 text-white sm:px-11">
        <Link href="/dashboard" className="flex items-center gap-3 font-serif text-xl">
          <Image src="/ub_voice.png" alt="Ubuntu Voice" width={48} height={48} className="size-11 rounded-full object-cover" priority />
          Ubuntu Voice
        </Link>
        <Link href="/" className="ml-4 hidden items-center gap-1.5 rounded-full border border-white/25 px-4 py-2 text-sm text-white/90 hover:bg-white/10 sm:flex">
          <Home className="size-4" aria-hidden />
          Home
        </Link>
        <ProfileMenu name={name} />
      </header>

      <div className="mx-auto flex min-h-[calc(100svh-91px)] max-w-[1900px] flex-col md:flex-row">
        <aside className="w-full shrink-0 border-b border-[#dce4ef] bg-white px-4 py-3 md:w-[224px] md:border-b-0 md:border-r md:px-3 md:py-5">
          <nav className="grid grid-cols-2 gap-1 sm:grid-cols-4 md:flex md:flex-col" aria-label="Dashboard navigation">
            <DashboardLink href="/dashboard" label="Overview" icon={Home} active />
            <DashboardLink href="/usage" label="Usage" icon={Gauge} />
            <DashboardLink href="/guardrails" label="Guardrails" icon={ShieldAlert} />
            <DashboardLink href="/evaluations" label="Evaluations" icon={BarChart3} />
          </nav>
        </aside>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-7 sm:py-8 lg:px-10">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="font-serif text-3xl sm:text-[29px]">Good afternoon, {name}</h1>
              <p className="mt-1 font-serif text-lg text-[#607694]">Your area status is calm. Last checked 2 minutes ago.</p>
            </div>
            <button type="button" className="rounded-2xl bg-[#e52327] px-10 py-5 font-serif text-lg text-white shadow-sm hover:bg-[#c91c20]">Send SOS alert</button>
          </div>

          <section className="mt-6 grid gap-3 lg:grid-cols-3" aria-label="Safety summary">
            <SummaryCard label="Active responders nearby" value="3" />
            <SummaryCard label="Your open reports" value="1" />
            <SummaryCard label="Connection" value="Stable" value_class="text-[#008575]" />
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <Panel title="Recent activity">
              <ActivityRow tone="red" title="Incident reported near Kibera market" detail="12 minutes ago · responder notified" />
              <ActivityRow tone="blue" title="Guidance requested on safe routes" detail="1 hour ago · resolved" />
              <ActivityRow tone="green" title="Weekly safety check-in completed" detail="Yesterday" />
            </Panel>
            <Panel title="Nearby responders">
              <ResponderRow name="Community safety desk" distance="0.8 km away" status="active" />
              <ResponderRow name="Red Cross field unit" distance="2.1 km away" status="active" />
              <ResponderRow name="Local mediator network" distance="3.4 km away" status="standby" />
            </Panel>
          </section>
        </main>
      </div>
    </div>
  )
}

function DashboardLink({ href, label, icon: Icon, active = false }: { href: string; label: string; icon: typeof Home; active?: boolean }) {
  return <Link href={href} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors md:px-4 ${active ? "bg-[#eef5ff] font-medium text-[#123f88]" : "text-[#607694] hover:bg-[#f4f7fb] hover:text-[#123f88]"}`}><Icon className="size-4" aria-hidden />{label}</Link>
}

function SummaryCard({ label, value, value_class = "" }: { label: string; value: string; value_class?: string }) {
  return <div className="rounded-xl border border-[#dce4ef] bg-white px-4 py-3"><p className="font-serif text-sm text-[#607694]">{label}</p><p className={`mt-1 font-serif text-2xl ${value_class}`}>{value}</p></div>
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-xl border border-[#dce4ef] bg-white px-4 py-4"><h2 className="font-serif text-lg">{title}</h2><div className="mt-3">{children}</div></section>
}

function ActivityRow({ tone, title, detail }: { tone: "red" | "blue" | "green"; title: string; detail: string }) {
  const colors = { red: "bg-[#ffe1e1]", blue: "bg-[#edf4ff]", green: "bg-[#e8fbf3]" }
  return <div className="flex min-w-0 items-center gap-3 border-b border-[#edf1f6] py-2.5 last:border-0"><span className={`size-9 shrink-0 rounded-lg ${colors[tone]}`} /><div className="min-w-0"><p className="truncate font-serif text-base">{title}</p><p className="truncate font-serif text-xs text-[#8aa0bd]">{detail}</p></div></div>
}

function ResponderRow({ name, distance, status }: { name: string; distance: string; status: "active" | "standby" }) {
  return <div className="flex items-center justify-between gap-3 border-b border-[#edf1f6] py-2.5 last:border-0"><div className="min-w-0"><p className="truncate font-serif text-base">{name}</p><p className="font-serif text-xs text-[#8aa0bd]">{distance}</p></div><span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] ${status === "active" ? "bg-[#dff5ee] text-[#178574]" : "bg-[#fff0d9] text-[#a26500]"}`}>{status}</span></div>
}
