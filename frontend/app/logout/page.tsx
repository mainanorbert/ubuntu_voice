"use client"

import { useEffect } from "react"
import { Loader2 } from "lucide-react"

export default function LogoutPage() {
  useEffect(() => {
    void fetch("/api/auth/logout", { method: "POST" }).finally(() => {
      window.location.replace("/")
    })
  }, [])

  return (
    <main className="flex min-h-svh items-center justify-center bg-background text-sm text-muted-foreground">
      <Loader2 className="mr-2 size-4 animate-spin" />
      Signing out...
    </main>
  )
}
