"use client"

import Image from "next/image"
import Link from "next/link"
import { Menu, X } from "lucide-react"
import { useEffect, useState } from "react"
import { usePathname } from "next/navigation"

import { ProfileMenu } from "@/components/profile-menu"
import { ThemeToggle } from "@/components/theme-toggle"

const links = [
  { href: "/chat", label: "Chat" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/documents", label: "Create Agent" },
]

/** Provides the shared responsive navigation for public and authenticated pages. */
export function AppNavbar({ is_signed_in = false }: { is_signed_in?: boolean }) {
  const pathname = usePathname()
  const [open, set_open] = useState(false)
  const [profile_name, set_profile_name] = useState<string | undefined>()

  useEffect(() => {
    if (!is_signed_in) return
    fetch("/api/auth/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((profile: { name?: unknown } | null) => {
        if (typeof profile?.name === "string" && profile.name.trim()) set_profile_name(profile.name)
      })
      .catch(() => undefined)
  }, [is_signed_in])

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#1E3A8A] bg-[#1E3A8A]/95 px-4 shadow-sm backdrop-blur sm:px-7">
      <div className="mx-auto flex h-[68px] max-w-[1900px] items-center gap-3">
        <Link href="/" className="flex items-center gap-2 rounded-full bg-gradient-to-r from-[#2864e8] to-[#24479c] px-3 py-2 text-sm font-semibold text-white">
          <Image src="/ub_voice.png" alt="Ubuntu Voice" width={28} height={28} className="size-7 rounded-full object-cover" priority />
          <span className="hidden sm:inline">Ubuntu Voice</span>
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
          {(is_signed_in ? links : []).map((link) => <Link key={link.href} href={link.href} className={`rounded-lg px-3 py-2 text-sm ${pathname === link.href ? "bg-white/15 font-medium text-white" : "text-[#dbeafe] hover:bg-white/10 hover:text-white"}`}>{link.label}</Link>)}
        </nav>
        <div className="flex-1" />
        <div className="hidden items-center gap-2 sm:flex"><ThemeToggle />{is_signed_in ? <ProfileMenu name={profile_name} /> : <><Link href="/login" className="rounded-full border border-[#93c5fd] px-4 py-2 text-sm text-white hover:bg-white/10">Sign in</Link><Link href="/register" className="rounded-full bg-[#2563EB] px-4 py-2 text-sm text-white hover:bg-[#60A5FA]">Sign up</Link></>}</div>
        <button type="button" onClick={() => set_open((value) => !value)} className="cursor-pointer rounded-lg p-2 text-white md:hidden" aria-label="Toggle navigation">{open ? <X /> : <Menu />}</button>
      </div>
      {open ? <nav className="flex flex-col gap-1 border-t border-white/20 py-3 md:hidden">{(is_signed_in ? links : []).map((link) => <Link key={link.href} href={link.href} onClick={() => set_open(false)} className="rounded-lg px-3 py-2 text-sm text-[#dbeafe] hover:bg-white/10 hover:text-white">{link.label}</Link>)}<div className="flex items-center gap-3 px-3 pt-2"><ThemeToggle />{is_signed_in ? <ProfileMenu name={profile_name} /> : <><Link href="/login" className="text-sm text-white">Sign in</Link><Link href="/register" className="text-sm text-white">Sign up</Link></>}</div></nav> : null}
    </header>
  )
}
