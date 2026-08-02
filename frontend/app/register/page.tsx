import Image from "next/image"
import Link from "next/link"
import { Suspense } from "react"

import { AuthForm } from "@/components/auth-form"

export default function RegisterPage() {
  return (
    <main className="flex min-h-svh flex-col bg-[#f7f9fc]">
      <header className="flex h-[88px] items-center justify-between border-b border-[#dce4ef] px-5 sm:px-10">
        <Link href="/" className="flex items-center gap-3">
          <Image src="/ub_voice.png" alt="Ubuntu Voice" width={48} height={48} className="size-12 rounded-full object-cover" />
          <span className="text-xl font-semibold text-[#101a32]">Ubuntu Voice</span>
        </Link>
        <Link href="/login" className="cursor-pointer rounded-full border border-[#dce4ef] bg-white px-5 py-2.5 text-sm font-medium text-[#123f88] hover:bg-[#eef5ff]">Sign in</Link>
      </header>
      <section className="flex flex-1 items-center justify-center px-4 py-10 sm:py-16">
        <Suspense>
          <AuthForm mode="register" />
        </Suspense>
      </section>
    </main>
  )
}
