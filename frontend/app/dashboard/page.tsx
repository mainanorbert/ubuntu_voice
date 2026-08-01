"use client"

import { useEffect, useState } from "react"
import { CalendarDays, Loader2, Mail, UserRound } from "lucide-react"

import { DashboardShell } from "@/components/dashboard-shell"

type CurrentUser = {
  id: string
  email: string | null
  name: string | null
  avatar_url: string | null
  created_at: string
}

/**
 * Formats a timestamp into a readable local date.
 */
function format_date(timestamp: string | null | undefined): string {
  if (!timestamp) return "Not available"
  return new Date(timestamp).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

export default function DashboardPage() {
  const [user, set_user] = useState<CurrentUser | null>(null)
  const [loading, set_loading] = useState(true)

  useEffect(() => {
    let active = true
    fetch("/api/auth/me", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Profile request failed")
        return (await response.json()) as CurrentUser
      })
      .then((profile) => {
        if (active) set_user(profile)
      })
      .catch(() => {
        if (active) set_user(null)
      })
      .finally(() => {
        if (active) set_loading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const display_name = user?.name || "Ubuntu Voice user"
  const email = user?.email || "No email available"

  return (
    <DashboardShell title="Dashboard" description="Your account overview and monitoring workspace.">
      {loading ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-5 py-16 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading your profile...
        </div>
      ) : (
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="flex size-16 items-center justify-center overflow-hidden rounded-full bg-primary/10 text-primary">
              {user?.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.avatar_url} alt="" className="size-full object-cover" referrerPolicy="no-referrer" />
              ) : (
                <UserRound className="size-8" />
              )}
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Signed in as</p>
              <h2 className="mt-1 text-xl font-semibold text-foreground">{display_name}</h2>
            </div>
          </div>

          <dl className="mt-6 grid gap-4 border-t border-border pt-6 sm:grid-cols-2">
            <div className="rounded-lg bg-muted/40 p-4">
              <dt className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Mail className="size-4 text-primary" />
                Email
              </dt>
              <dd className="mt-2 break-all text-sm text-foreground">{email}</dd>
            </div>
            <div className="rounded-lg bg-muted/40 p-4">
              <dt className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <CalendarDays className="size-4 text-primary" />
                Member since
              </dt>
              <dd className="mt-2 text-sm text-foreground">{format_date(user?.created_at)}</dd>
            </div>
          </dl>
        </section>
      )}
    </DashboardShell>
  )
}
