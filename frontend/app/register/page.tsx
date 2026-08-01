import Image from "next/image"
import Link from "next/link"
import { Suspense } from "react"

import { AuthForm } from "@/components/auth-form"
import { ThemeToggle } from "@/components/theme-toggle"

export default function RegisterPage() {
  return (
    <main className="flex min-h-svh flex-col bg-background">
      <header className="flex h-16 items-center justify-between border-b border-border/60 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-3">
          <Image src="/ub_voice.png" alt="Ubuntu Voice" width={180} height={48} className="h-9 w-auto" />
        </Link>
        <ThemeToggle />
      </header>
      <section className="flex flex-1 items-center justify-center px-4 py-10">
        <Suspense>
          <AuthForm mode="register" />
        </Suspense>
      </section>
    </main>
  )
}
