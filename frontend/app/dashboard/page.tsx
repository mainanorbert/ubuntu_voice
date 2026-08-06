"use client"

import Link from "next/link"
import { useCallback, useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import { BarChart3, Gauge, Home, Loader2, Map, ShieldAlert } from "lucide-react"
import { AppNavbar } from "@/components/app-navbar"
import { IncidentHotspotMap } from "@/components/incident-hotspot-map"
import type {
  IncidentStatistic,
  KnownPlace,
} from "@/components/incident-hotspot-map"

type CurrentUser = { name: string | null }
type Agent = { id: string; name: string }
type IncidentStatisticsPage = {
  items: IncidentStatistic[]
  total: number
  agents: Agent[]
}

function is_incident_statistics_page(
  value: unknown
): value is IncidentStatisticsPage {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as IncidentStatisticsPage).items) &&
    typeof (value as IncidentStatisticsPage).total === "number" &&
    Array.isArray((value as IncidentStatisticsPage).agents)
  )
}

/** Renders the calm, low-bandwidth community safety dashboard overview. */
export default function DashboardPage() {
  const [user, set_user] = useState<CurrentUser | null>(null)
  const [statistics, set_statistics] = useState<IncidentStatistic[]>([])
  const [known_places, set_known_places] = useState<KnownPlace[]>([])
  const [map_loading, set_map_loading] = useState(true)
  const [map_error, set_map_error] = useState<string | null>(null)
  const [map_agent_id, set_map_agent_id] = useState("")
  const [map_agents, set_map_agents] = useState<Agent[]>([])
  const map_agent_id_ref = useRef(map_agent_id)

  useEffect(() => {
    map_agent_id_ref.current = map_agent_id
  }, [map_agent_id])

  const load_hotspot_data = useCallback(
    async (agent_id = map_agent_id_ref.current) => {
      try {
        const all_statistics: IncidentStatistic[] = []
        let page = 1
        let total = 0
        let agents: Agent[] = []

        do {
          const search = new URLSearchParams({
            page: String(page),
            page_size: "100",
          })
          if (agent_id) search.set("agent_id", agent_id)
          const [statistics_response, places_response] = await Promise.all([
            fetch(`/api/monitoring/incident-statistics?${search}`, {
              cache: "no-store",
            }),
            page === 1
              ? fetch("/api/monitoring/known-places", { cache: "no-store" })
              : Promise.resolve(null),
          ])
          if (
            !statistics_response.ok ||
            (places_response && !places_response.ok)
          ) {
            set_map_error(
              "Incident locations are temporarily unavailable. Please try again later."
            )
            return
          }
          const statistics_data: unknown = await statistics_response.json()
          const places_data: unknown = places_response
            ? await places_response.json()
            : null
          if (
            !is_incident_statistics_page(statistics_data) ||
            (places_data !== null && !Array.isArray(places_data))
          ) {
            set_map_error("Incident locations could not be loaded right now.")
            return
          }
          all_statistics.push(...statistics_data.items)
          total = statistics_data.total
          agents = statistics_data.agents
          if (places_data !== null) set_known_places(places_data)
          page += 1
        } while (all_statistics.length < total)

        set_statistics(all_statistics)
        set_map_agents(agents)
        set_map_error(null)
      } catch {
        set_map_error(
          "Incident locations are temporarily unavailable. Please try again later."
        )
      } finally {
        set_map_loading(false)
      }
    },
    []
  )

  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((profile: CurrentUser | null) => set_user(profile))
      .catch(() => set_user(null))

    const initial_load = window.setTimeout(() => void load_hotspot_data(), 0)
    const refresh_map = () => void load_hotspot_data(map_agent_id_ref.current)
    window.addEventListener("known-places-updated", refresh_map)
    window.addEventListener("focus", refresh_map)
    const place_updates =
      typeof BroadcastChannel === "undefined"
        ? null
        : new BroadcastChannel("known-places-updated")
    place_updates?.addEventListener("message", refresh_map)

    return () => {
      window.clearTimeout(initial_load)
      window.removeEventListener("known-places-updated", refresh_map)
      window.removeEventListener("focus", refresh_map)
      place_updates?.close()
    }
  }, [load_hotspot_data])

  const name = user?.name || "Ubuntu Voice user"

  return (
    <div className="min-h-svh bg-[#f7f9fc] text-[#061b3b]">
      <AppNavbar is_signed_in />

      <div className="mx-auto flex min-h-[calc(100svh-91px)] max-w-[1900px] flex-col md:flex-row">
        <aside className="w-full shrink-0 border-b border-[#dce4ef] bg-white px-4 py-3 md:w-[224px] md:border-r md:border-b-0 md:px-3 md:py-5">
          <nav
            className="grid grid-cols-2 gap-1 sm:grid-cols-4 md:flex md:flex-col"
            aria-label="Dashboard navigation"
          >
            <DashboardLink
              href="/dashboard"
              label="Overview"
              icon={Home}
              active
            />
            <DashboardLink href="/usage" label="Usage" icon={Gauge} />
            <DashboardLink
              href="/guardrails"
              label="Guardrails"
              icon={ShieldAlert}
            />
            <DashboardLink
              href="/evaluations"
              label="Evaluations"
              icon={BarChart3}
            />
            <DashboardLink
              href="/statistics"
              label="Statistics"
              icon={BarChart3}
            />
          </nav>
        </aside>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-7 sm:py-8 lg:px-10">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="font-serif text-3xl sm:text-[29px]">
                Good afternoon, {name}
              </h1>
              <p className="mt-1 font-serif text-lg text-[#607694]">
                Your area status is calm. Last checked 2 minutes ago.
              </p>
            </div>
          </div>

          <section
            className="mt-6 grid gap-3 lg:grid-cols-3"
            aria-label="Safety summary"
          >
            <SummaryCard label="Active responders nearby" value="3" />
            <SummaryCard label="Your open reports" value="1" />
            <SummaryCard
              label="Connection"
              value="Stable"
              value_class="text-[#008575]"
            />
          </section>

          <section
            className="mt-6 overflow-hidden rounded-xl border border-[#dce4ef] bg-white shadow-sm"
            aria-labelledby="hotspot-map-title"
          >
            <div className="flex flex-col gap-3 border-b border-[#dce4ef] px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
              <div>
                <div className="flex items-center gap-2">
                  <Map className="size-5 text-[#2563EB]" aria-hidden="true" />
                  <h2 id="hotspot-map-title" className="font-serif text-lg">
                    Incident hotspots
                  </h2>
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-[#607694]">
                Agent
                <select
                  value={map_agent_id}
                  onChange={(event) => {
                    const agent_id = event.target.value
                    map_agent_id_ref.current = agent_id
                    set_map_agent_id(agent_id)
                    void load_hotspot_data(agent_id)
                  }}
                  className="rounded-lg border border-[#b9cdeb] bg-white px-2 py-1.5 text-[#1E3A8A] outline-none focus:ring-2 focus:ring-[#60A5FA]"
                >
                  <option value="">All agents</option>
                  {map_agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </label>
              <div
                className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-[#607694]"
                aria-label="Map legend"
              >
                <span>
                  <i className="mr-1 inline-block size-2.5 rounded-full bg-[#DC2626]" />
                  Rights Violations
                </span>
                <span>
                  <i className="mr-1 inline-block size-2.5 rounded-full bg-[#F97316]" />
                  Casualties
                </span>
                <span>
                  <i className="mr-1 inline-block size-2.5 rounded-full bg-[#2563EB]" />
                  Displacements
                </span>
                <span>
                  <i className="mr-1 inline-block size-2.5 rounded-full bg-[#EAB308]" />
                  Severe Hunger
                </span>
              </div>
            </div>
            {map_loading ? (
              <div
                className="flex h-[360px] items-center justify-center gap-2 text-sm text-[#607694] sm:h-[460px]"
                role="status"
              >
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />{" "}
                Loading incident hotspots...
              </div>
            ) : map_error ? (
              <div
                className="flex h-[360px] items-center justify-center px-5 text-center text-sm text-[#DC2626] sm:h-[460px]"
                role="alert"
              >
                {map_error}
              </div>
            ) : statistics.length === 0 ? (
              <div className="flex h-[360px] items-center justify-center px-5 text-center text-sm text-[#607694] sm:h-[460px]">
                No incident statistics have been recorded yet.
              </div>
            ) : (
              <IncidentHotspotMap
                statistics={statistics}
                known_places={known_places}
              />
            )}
          </section>

          <section className="mt-6 grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <Panel title="Recent activity">
              <ActivityRow
                tone="red"
                title="Incident reported near Kibera market"
                detail="12 minutes ago · responder notified"
              />
              <ActivityRow
                tone="blue"
                title="Guidance requested on safe routes"
                detail="1 hour ago · resolved"
              />
              <ActivityRow
                tone="green"
                title="Weekly safety check-in completed"
                detail="Yesterday"
              />
            </Panel>
            <Panel title="Nearby responders">
              <ResponderRow
                name="Community safety desk"
                distance="0.8 km away"
                status="active"
              />
              <ResponderRow
                name="Red Cross field unit"
                distance="2.1 km away"
                status="active"
              />
              <ResponderRow
                name="Local mediator network"
                distance="3.4 km away"
                status="standby"
              />
            </Panel>
          </section>
        </main>
      </div>
    </div>
  )
}

function DashboardLink({
  href,
  label,
  icon: Icon,
  active = false,
}: {
  href: string
  label: string
  icon: typeof Home
  active?: boolean
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors md:px-4 ${active ? "bg-[#eef5ff] font-medium text-[#123f88]" : "text-[#607694] hover:bg-[#f4f7fb] hover:text-[#123f88]"}`}
    >
      <Icon className="size-4" aria-hidden />
      {label}
    </Link>
  )
}

function SummaryCard({
  label,
  value,
  value_class = "",
}: {
  label: string
  value: string
  value_class?: string
}) {
  return (
    <div className="rounded-xl border border-[#dce4ef] bg-white px-4 py-3">
      <p className="font-serif text-sm text-[#607694]">{label}</p>
      <p className={`mt-1 font-serif text-2xl ${value_class}`}>{value}</p>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-[#dce4ef] bg-white px-4 py-4">
      <h2 className="font-serif text-lg">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function ActivityRow({
  tone,
  title,
  detail,
}: {
  tone: "red" | "blue" | "green"
  title: string
  detail: string
}) {
  const colors = {
    red: "bg-[#ffe1e1]",
    blue: "bg-[#edf4ff]",
    green: "bg-[#e8fbf3]",
  }
  return (
    <div className="flex min-w-0 items-center gap-3 border-b border-[#edf1f6] py-2.5 last:border-0">
      <span className={`size-9 shrink-0 rounded-lg ${colors[tone]}`} />
      <div className="min-w-0">
        <p className="truncate font-serif text-base">{title}</p>
        <p className="truncate font-serif text-xs text-[#8aa0bd]">{detail}</p>
      </div>
    </div>
  )
}

function ResponderRow({
  name,
  distance,
  status,
}: {
  name: string
  distance: string
  status: "active" | "standby"
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[#edf1f6] py-2.5 last:border-0">
      <div className="min-w-0">
        <p className="truncate font-serif text-base">{name}</p>
        <p className="font-serif text-xs text-[#8aa0bd]">{distance}</p>
      </div>
      <span
        className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] ${status === "active" ? "bg-[#dff5ee] text-[#178574]" : "bg-[#fff0d9] text-[#a26500]"}`}
      >
        {status}
      </span>
    </div>
  )
}
