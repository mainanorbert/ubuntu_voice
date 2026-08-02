import Image from "next/image"
import Link from "next/link"
import { Suspense } from "react"

import { AuthForm } from "@/components/auth-form"

export default function LoginPage() {
  return (
    <main className="flex min-h-svh flex-col bg-[#f7f9fc]">
      <header className="flex h-[88px] items-center justify-between border-b border-[#dce4ef] px-5 sm:px-10">
        <Link href="/" className="flex items-center gap-3">
          <Image src="/ub_voice.png" alt="Ubuntu Voice" width={48} height={48} className="size-12 rounded-full object-cover" />
          <span className="text-xl font-semibold text-[#101a32]">Ubuntu Voice</span>
        </Link>
        <Link href="/register" className="cursor-pointer rounded-full bg-[#2864e8] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#1f56ce]">Register</Link>
      </header>
      <section className="flex flex-1 items-center justify-center px-4 py-10 sm:py-16">
        <Suspense>
          <AuthForm mode="login" />
        </Suspense>
      </section>
    </main>
  )
}
