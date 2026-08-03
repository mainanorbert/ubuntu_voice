"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { FormEvent, ReactNode, useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"

type ApiResponse = { detail?: unknown; error?: unknown; message?: unknown }

/** Collects an email address and sends a non-enumerating password-reset request. */
export function ForgotPasswordForm() {
  const [loading, set_loading] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const [message, set_message] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    set_error(null)
    set_message(null)
    set_loading(true)
    const form = new FormData(event.currentTarget)
    try {
      const response = await fetch("/api/auth/password-reset/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: String(form.get("email") ?? "").trim() }) })
      const data = (await response.json().catch(() => ({}))) as ApiResponse
      if (!response.ok) {
        set_error(read_error(data))
        return
      }
      set_message(typeof data.message === "string" ? data.message : "Check your email for a password reset link.")
    } catch {
      set_error("We’re unable to send a reset email right now. Please try again in a few minutes.")
    } finally {
      set_loading(false)
    }
  }

  return <AuthCard title="Reset your password" description="Enter your email and we’ll send a link to reset your password."><form className="space-y-4" onSubmit={submit}><label className="block text-sm font-medium text-[#123f88]">Email<input name="email" type="email" autoComplete="email" required className={input_class} placeholder="you@example.com" /></label><Feedback error={error} message={message} /><Button type="submit" className="h-11 w-full rounded-full bg-[#2563EB] text-white hover:bg-[#1E3A8A]" disabled={loading}>{loading ? <Loader2 className="size-4 animate-spin" /> : null}Send reset link</Button></form><p className="mt-6 text-center text-sm text-[#607694]"><Link className="font-medium text-[#2563EB] hover:underline" href="/login">Back to sign in</Link></p></AuthCard>
}

/** Validates the link token and accepts a confirmed replacement password. */
export function ResetPasswordForm() {
  const router = useRouter()
  const token = useSearchParams().get("token") ?? ""
  const [loading, set_loading] = useState(false)
  const [error, set_error] = useState<string | null>(token ? null : "This password reset link is invalid or incomplete.")

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token) return
    set_error(null)
    const form = new FormData(event.currentTarget)
    const password = String(form.get("password") ?? "")
    if (!is_strong_password(password)) return set_error("Use at least 12 characters with uppercase, lowercase, a number, and a symbol.")
    if (password !== String(form.get("confirm_password") ?? "")) return set_error("Passwords do not match.")
    set_loading(true)
    try {
      const response = await fetch("/api/auth/password-reset/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, password }) })
      const data = (await response.json().catch(() => ({}))) as ApiResponse
      if (!response.ok) return set_error(read_error(data))
      router.replace("/login?reset=success")
    } catch {
      set_error("We couldn’t reset your password right now. Please try again in a few minutes.")
    } finally {
      set_loading(false)
    }
  }

  return <AuthCard title="Choose a new password" description="Create a secure password for your account."><form className="space-y-4" onSubmit={submit}><label className="block text-sm font-medium text-[#123f88]">New password<input name="password" type="password" autoComplete="new-password" required minLength={12} className={input_class} placeholder="12+ characters" disabled={!token} /></label><p className="-mt-2 text-xs text-[#607694]">Use uppercase, lowercase, a number, and a symbol.</p><label className="block text-sm font-medium text-[#123f88]">Confirm new password<input name="confirm_password" type="password" autoComplete="new-password" required minLength={12} className={input_class} placeholder="Re-enter your password" disabled={!token} /></label><Feedback error={error} /><Button type="submit" className="h-11 w-full rounded-full bg-[#2563EB] text-white hover:bg-[#1E3A8A]" disabled={loading || !token}>{loading ? <Loader2 className="size-4 animate-spin" /> : null}Reset password</Button></form></AuthCard>
}

function AuthCard({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <div className="w-full max-w-md rounded-3xl border border-[#dce4ef] bg-white p-6 shadow-lg shadow-[#123f88]/5 sm:p-8"><h1 className="text-2xl font-semibold tracking-tight text-[#101a32]">{title}</h1><p className="mt-2 text-sm text-[#607694]">{description}</p><div className="mt-6">{children}</div></div>
}

function Feedback({ error, message }: { error?: string | null; message?: string | null }) {
  if (error) return <p className="rounded-xl border border-destructive/25 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
  if (message) return <p className="rounded-xl border border-[#60A5FA] bg-[#eff6ff] px-3 py-2 text-sm text-[#1E3A8A]">{message}</p>
  return null
}

const input_class = "mt-2 h-11 w-full rounded-xl border border-[#b9cdeb] bg-white px-3 text-sm outline-none transition focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 disabled:cursor-not-allowed disabled:bg-[#f8fafc]"

function is_strong_password(password: string): boolean {
  return password.length >= 12 && /[a-z]/.test(password) && /[A-Z]/.test(password) && /\d/.test(password) && /[^A-Za-z0-9]/.test(password)
}

function read_error(data: ApiResponse): string {
  const raw = data.detail ?? data.error
  return typeof raw === "string" ? raw : "Please check the form and try again."
}
