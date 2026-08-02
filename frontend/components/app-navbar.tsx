"use client"

import Image from "next/image"
import Link from "next/link"
import { Menu, X } from "lucide-react"
import { useState } from "react"
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

  return (
    <header className="sticky top-0 z-50 border-b border-[#dce4ef] bg-white/95 px-4 shadow-sm backdrop-blur dark:border-[#294263] dark:bg-[#101d33]/95 sm:px-7">
      <div className="mx-auto flex h-[68px] max-w-[1900px] items-center gap-3">
        <Link href="/" className="flex items-center gap-2 rounded-full bg-gradient-to-r from-[#2864e8] to-[#24479c] px-3 py-2 text-sm font-semibold text-white">
          <Image src="/ub_voice.png" alt="Ubuntu Voice" width={28} height={28} className="size-7 rounded-full object-cover" priority />
          <span className="hidden sm:inline">Ubuntu Voice</span>
        </Link>
        {is_signed_in ? <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
          {links.map((link) => <Link key={link.href} href={link.href} className={`rounded-lg px-3 py-2 text-sm ${pathname === link.href ? "bg-[#eef5ff] font-medium text-[#2864e8]" : "text-[#607694] hover:bg-[#f4f7fb]"}`}>{link.label}</Link>)}
        </nav> : null}
        <div className="flex-1" />
        <div className="hidden items-center gap-2 sm:flex"><ThemeToggle />{is_signed_in ? <ProfileMenu /> : <><Link href="/login" className="rounded-full border border-[#dce4ef] px-4 py-2 text-sm text-[#607694]">Sign in</Link><Link href="/register" className="rounded-full bg-[#2864e8] px-4 py-2 text-sm text-white">Register</Link></>}</div>
        <button type="button" onClick={() => set_open((value) => !value)} className="cursor-pointer rounded-lg p-2 text-[#607694] md:hidden" aria-label="Toggle navigation">{open ? <X /> : <Menu />}</button>
      </div>
      {open ? <nav className="flex flex-col gap-1 border-t border-[#dce4ef] py-3 md:hidden">{is_signed_in ? links.map((link) => <Link key={link.href} href={link.href} onClick={() => set_open(false)} className="rounded-lg px-3 py-2 text-sm text-[#607694] hover:bg-[#eef5ff]">{link.label}</Link>) : null}<div className="flex items-center gap-3 px-3 pt-2"><ThemeToggle />{is_signed_in ? <ProfileMenu /> : <Link href="/login" className="text-sm text-[#2864e8]">Sign in</Link>}</div></nav> : null}
    </header>
  )
}
