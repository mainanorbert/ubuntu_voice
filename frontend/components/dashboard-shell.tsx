"use client"

import {
  BarChart3,
  Gauge,
  Home,
  MapPin,
  ShieldAlert,
  Table2,
} from "lucide-react"
import { AppNavbar } from "@/components/app-navbar"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useState } from "react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

const dashboard_links = [
  { href: "/dashboard", label: "Overview", icon: Home },
  { href: "/guardrails", label: "Guardrails", icon: ShieldAlert },
  { href: "/statistics", label: "Statistics", icon: Table2 },
  { href: "/places", label: "Known Places", icon: MapPin },
  { href: "/evaluations", label: "Evaluations", icon: BarChart3 },
]

type DashboardShellProps = {
  children: ReactNode
  title: string
  description: string
}

/**
 * Provides shared dashboard navigation and account controls for monitoring pages.
 */
export function DashboardShell({
  children,
  title,
  description,
}: DashboardShellProps) {
  const pathname = usePathname()
  const [is_admin, set_is_admin] = useState(false)

  useEffect(() => {
    void fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((profile: { is_admin?: unknown } | null) =>
        set_is_admin(profile?.is_admin === true)
      )
      .catch(() => set_is_admin(false))
  }, [])

  const visible_links = is_admin
    ? [
        ...dashboard_links,
        { href: "/usage", label: "Usage", icon: Gauge },
        { href: "/admin", label: "Agent approvals", icon: ShieldAlert },
      ]
    : dashboard_links

  return (
    <div className="min-h-svh bg-[#f7f9fc] text-[#061b3b]">
      <AppNavbar is_signed_in />

      <div className="mx-auto flex max-w-[1900px] flex-col md:min-h-[calc(100svh-68px)] md:flex-row">
        <aside className="border-b border-[#dce4ef] bg-white p-2 md:w-56 md:shrink-0 md:border-r md:border-b-0 md:p-3">
          <nav
            className="grid grid-cols-2 gap-1 sm:grid-cols-4 md:flex md:flex-col"
            aria-label="Dashboard navigation"
          >
            {visible_links.map((link) => {
              const Icon = link.icon
              const is_active = pathname === link.href

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                    is_active
                      ? "bg-[#eef5ff] font-medium text-[#123f88]"
                      : "text-[#607694] hover:bg-[#f4f7fb] hover:text-[#123f88]"
                  )}
                >
                  <Icon className="size-4" />
                  {link.label}
                </Link>
              )
            })}
          </nav>
        </aside>

        <main className="min-w-0 flex-1 px-4 py-5 sm:px-7 sm:py-7 lg:px-10">
          <div className="mb-5">
            <h1 className="font-serif text-2xl tracking-tight text-[#061b3b]">
              {title}
            </h1>
            <p className="mt-1 text-sm text-[#607694]">{description}</p>
          </div>
          {children}
        </main>
      </div>
    </div>
  )
}
