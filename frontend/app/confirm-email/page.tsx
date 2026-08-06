import { Suspense } from "react"

import { AppNavbar } from "@/components/app-navbar"
import { EmailVerificationForm } from "@/components/email-verification-form"

export default function ConfirmEmailPage() {
  return <main className="flex min-h-svh flex-col bg-[#F8FAFC]"><AppNavbar is_signed_in={false} /><section className="flex flex-1 items-center justify-center px-4 py-10 sm:py-16"><Suspense><EmailVerificationForm /></Suspense></section></main>
}
