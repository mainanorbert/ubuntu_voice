"use client"

import { useUser } from "@clerk/nextjs"
import { CalendarDays, Loader2, Mail, UserRound } from "lucide-react"

import { DashboardShell } from "@/components/dashboard-shell"

/**
 * Formats a timestamp into a readable local date.
 */
function format_date(timestamp: number | null | undefined): string {
  if (!timestamp) return "Not available"
  return new Date(timestamp).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

export default function DashboardPage() {
  const { isLoaded, user } = useUser()
  const display_name = user?.fullName || user?.firstName || "Ubuntu Voice user"
  const email = user?.primaryEmailAddress?.emailAddress || "No primary email available"

  return (
    <DashboardShell title="Dashboard" description="Your account overview and monitoring workspace.">
      {!isLoaded ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-5 py-16 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading your profile...
        </div>
      ) : (
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="flex size-16 items-center justify-center rounded-full bg-primary/10 text-primary">
              <UserRound className="size-8" />
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
              <dd className="mt-2 text-sm text-foreground">{format_date(user?.createdAt?.getTime())}</dd>
            </div>
          </dl>
        </section>
      )}
    </DashboardShell>
  )
}
