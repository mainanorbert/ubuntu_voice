"use client"

import { UserButton } from "@clerk/nextjs"
import { ArrowLeft, BarChart3, Gauge, Home, MessageSquare, ShieldAlert } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"

import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const dashboard_links = [
  { href: "/dashboard", label: "Overview", icon: Home },
  { href: "/usage", label: "Usage", icon: Gauge },
  { href: "/guardrails", label: "Guardrails", icon: ShieldAlert },
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
export function DashboardShell({ children, title, description }: DashboardShellProps) {
  const pathname = usePathname()
  const show_home_back_link = pathname === "/dashboard"

  return (
    <div className="min-h-svh bg-background">
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/90 px-4 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3">
          {show_home_back_link ? (
            <Button variant="ghost" size="sm" asChild>
              <Link href="/">
                <ArrowLeft className="size-4" />
                Home
              </Link>
            </Button>
          ) : null}
          <Link href="/dashboard" className="font-semibold text-foreground">
            Ubuntu Voice
          </Link>
          <div className="flex-1" />
          <Button variant="outline" size="sm" className="hidden sm:inline-flex" asChild>
            <Link href="/chat">
              <MessageSquare />
              Chat
            </Link>
          </Button>
          <ThemeToggle />
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl flex-col md:min-h-[calc(100svh-3.5rem)] md:flex-row">
        <aside className="border-b border-border bg-card/40 p-3 md:w-60 md:shrink-0 md:border-r md:border-b-0 md:p-4">
          <nav className="flex gap-2 overflow-x-auto md:flex-col" aria-label="Dashboard navigation">
            {dashboard_links.map((link) => {
              const Icon = link.icon
              const is_active = pathname === link.href

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    is_active
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="size-4" />
                  {link.label}
                </Link>
              )
            })}
          </nav>
        </aside>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          </div>
          {children}
        </main>
      </div>
    </div>
  )
}
