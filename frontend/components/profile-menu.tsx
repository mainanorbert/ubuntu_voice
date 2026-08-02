"use client"

import Link from "next/link"
import { useState } from "react"

/** Renders a compact initials avatar with an explicit logout menu. */
export function ProfileMenu({ name = "Ubuntu Voice user" }: { name?: string }) {
  const [open, set_open] = useState(false)
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "U"

  return (
    <div className="relative">
      <button type="button" onClick={() => set_open((value) => !value)} className="flex size-10 cursor-pointer items-center justify-center rounded-full bg-[#2864e8] text-sm font-semibold text-white hover:bg-[#1f56ce]" aria-label="Open profile menu" aria-expanded={open}>
        {initials}
      </button>
      {open ? <div className="absolute right-0 top-12 z-50 w-48 rounded-xl border border-[#dce4ef] bg-white p-2 text-sm shadow-lg"><p className="truncate px-3 py-2 font-medium text-[#061b3b]">{name}</p><Link href="/logout" className="block cursor-pointer rounded-lg px-3 py-2 text-[#607694] hover:bg-[#f4f7fb] hover:text-[#123f88]">Logout</Link></div> : null}
    </div>
  )
}
