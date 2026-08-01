"use client"

import { Menu, X } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { Button } from "@/components/ui/button"

type MobileNavProps = {
  is_signed_in: boolean
}

/** Provides the home page navigation links for narrow screens. */
export function MobileNav({ is_signed_in }: MobileNavProps) {
  const [is_open, set_is_open] = useState(false)

  const links = is_signed_in
    ? [
        ["/chat", "Community chat"],
        ["/dashboard", "Dashboard"],
        ["/documents", "Create agent"],
        ["/statistics", "Statistics"],
        ["/logout", "Logout"],
      ]
    : [
        ["/login", "Sign in"],
        ["/register", "Register"],
      ]

  return (
    <div className="relative sm:hidden">
      <Button
        variant="outline"
        size="icon"
        aria-label={is_open ? "Close navigation menu" : "Open navigation menu"}
        aria-expanded={is_open}
        onClick={() => set_is_open((open) => !open)}
      >
        {is_open ? <X className="size-4" /> : <Menu className="size-4" />}
      </Button>
      {is_open ? (
        <nav
          className="absolute right-0 top-11 z-50 w-44 rounded-lg border border-border bg-background p-1.5 shadow-lg"
          aria-label="Mobile navigation"
        >
          {links.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              className="block rounded-lg px-3 py-2.5 text-sm font-medium text-foreground hover:bg-muted"
              onClick={() => set_is_open(false)}
            >
              {label}
            </Link>
          ))}
        </nav>
      ) : null}
    </div>
  )
}
