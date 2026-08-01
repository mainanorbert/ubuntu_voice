"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { FormEvent, useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"

type AuthFormProps = {
  mode: "login" | "register"
}

type ErrorPayload = {
  detail?: unknown
  error?: unknown
}

/**
 * Renders a minimal manual auth form plus Google OAuth entrypoint.
 */
export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter()
  const search_params = useSearchParams()
  const [error, set_error] = useState<string | null>(read_oauth_error(search_params.get("error")))
  const [loading, set_loading] = useState(false)
  const is_register = mode === "register"

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    set_error(null)
    set_loading(true)

    const form = new FormData(event.currentTarget)
    const payload = {
      email: String(form.get("email") ?? ""),
      password: String(form.get("password") ?? ""),
      ...(is_register ? { name: String(form.get("name") ?? "") } : {}),
    }

    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      const data = (await response.json().catch(() => ({}))) as ErrorPayload
      if (!response.ok) {
        set_error(read_error_message(data))
        return
      }
      router.replace(search_params.get("next") || "/dashboard")
      router.refresh()
    } catch {
      set_error("Could not reach the authentication service.")
    } finally {
      set_loading(false)
    }
  }

  return (
    <div className="w-full max-w-md rounded-3xl border border-border bg-card p-6 shadow-sm sm:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {is_register ? "Create your account" : "Sign in to Ubuntu Voice"}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {is_register
            ? "Register manually or continue with Google."
            : "Use your password or continue with Google."}
        </p>
      </div>

      <Button
        type="button"
        variant="outline"
        className="mt-6 h-11 w-full gap-3 border-[#dadce0] bg-white text-[#3c4043] hover:bg-[#f8fafd] dark:bg-white dark:text-[#3c4043]"
        asChild
      >
        <a href="/api/auth/google/start">
          <GoogleIcon />
          Continue with Google
        </a>
      </Button>

      <div className="my-6 flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs uppercase tracking-wide text-muted-foreground">or</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <form className="space-y-4" onSubmit={submit}>
        {is_register ? (
          <label className="block text-sm font-medium text-foreground">
            Name
            <input
              name="name"
              autoComplete="name"
              className="mt-2 h-11 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none ring-ring transition focus:ring-2"
              placeholder="Ubuntu Voice user"
            />
          </label>
        ) : null}
        <label className="block text-sm font-medium text-foreground">
          Email
          <input
            name="email"
            type="email"
            autoComplete="email"
            required
            className="mt-2 h-11 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none ring-ring transition focus:ring-2"
            placeholder="you@example.org"
          />
        </label>
        <label className="block text-sm font-medium text-foreground">
          Password
          <input
            name="password"
            type="password"
            autoComplete={is_register ? "new-password" : "current-password"}
            required
            minLength={8}
            className="mt-2 h-11 w-full rounded-xl border border-input bg-background px-3 text-sm outline-none ring-ring transition focus:ring-2"
            placeholder="At least 8 characters"
          />
        </label>

        {error ? (
          <p className="rounded-xl border border-destructive/25 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="h-11 w-full" disabled={loading}>
          {loading ? <Loader2 className="size-4 animate-spin" /> : null}
          {is_register ? "Create account" : "Sign in"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        {is_register ? "Already have an account?" : "Need an account?"}{" "}
        <Link className="font-medium text-foreground underline-offset-4 hover:underline" href={is_register ? "/login" : "/register"}>
          {is_register ? "Sign in" : "Register"}
        </Link>
      </p>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-5">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.24 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06L5.84 9.9C6.71 7.3 9.14 5.38 12 5.38z" />
    </svg>
  )
}

function read_error_message(data: ErrorPayload): string {
  const raw = data.detail ?? data.error
  if (typeof raw === "string") return raw
  if (Array.isArray(raw) && raw.length > 0) return "Please check the form fields and try again."
  return "Authentication failed."
}

function read_oauth_error(error: string | null): string | null {
  if (!error) return null
  if (error === "google_not_configured") return "Google sign-in is not configured."
  if (error === "google_state") return "Google sign-in expired. Please try again."
  if (error === "api_unavailable") return "Could not reach the API server."
  return "Google sign-in failed. Please try again."
}
