"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"

type ApiResponse = { detail?: unknown; error?: unknown }

/** Activates a pending manual registration using the token from its email link. */
export function EmailVerificationForm() {
  const router = useRouter()
  const token = useSearchParams().get("token") ?? ""
  const [loading, set_loading] = useState(false)
  const [error, set_error] = useState<string | null>(
    token ? null : "This email confirmation link is invalid or incomplete.",
  )

  async function confirm_email() {
    if (!token) return
    set_error(null)
    set_loading(true)
    try {
      const response = await fetch("/api/auth/email-verification/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      })
      const data = (await response.json().catch(() => ({}))) as ApiResponse
      if (!response.ok) {
        const detail = data.detail ?? data.error
        set_error(typeof detail === "string" ? detail : "We couldn’t confirm your email. Please request a new link.")
        return
      }
      router.replace("/")
      router.refresh()
    } catch {
      set_error("We’re unable to confirm your email right now. Please try again in a few minutes.")
    } finally {
      set_loading(false)
    }
  }

  return <div className="w-full max-w-md rounded-3xl border border-[#dce4ef] bg-white p-6 shadow-lg shadow-[#123f88]/5 sm:p-8"><h1 className="text-2xl font-semibold tracking-tight text-[#1E3A8A]">Confirm your email</h1><p className="mt-2 text-sm text-[#607694]">Confirming your email will finish creating your Ubuntu Voice account.</p>{error ? <p className="mt-6 rounded-xl border border-[#DC2626]/25 bg-[#DC2626]/10 px-3 py-2 text-sm text-[#DC2626]">{error}</p> : null}<Button type="button" className="mt-6 h-11 w-full rounded-full bg-[#2563EB] text-white hover:bg-[#1E3A8A]" disabled={loading || !token} onClick={confirm_email}>{loading ? <Loader2 className="size-4 animate-spin" /> : null}Confirm email</Button></div>
}
