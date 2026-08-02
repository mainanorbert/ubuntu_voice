import Link from "next/link"
import { cookies } from "next/headers"
import {
  ArrowRight,
  FileText,
  Globe2,
  Languages,
  MessageSquare,
  Radio,
  Shield,
  UsersRound,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { AppNavbar } from "@/components/app-navbar"

const AUTH_COOKIE_NAME = "ubuntu_voice_session"

/**
 * Renders a mission-focused homepage feature block.
 */
function feature_card({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon
  title: string
  description: string
}) {
  return (
    <div
      className={cn(
        "group relative rounded-2xl border border-border/80 bg-card/70 p-6 shadow-sm backdrop-blur-sm",
        "transition-colors hover:border-border hover:bg-card",
      )}
    >
      <div className="mb-4 inline-flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <Icon className="size-5" aria-hidden />
      </div>
      <h3 className="font-heading text-base font-semibold tracking-tight text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
    </div>
  )
}

export default async function Page() {
  const cookie_store = await cookies()
  const is_signed_in = Boolean(cookie_store.get(AUTH_COOKIE_NAME)?.value)

  return (
    <div className="relative flex min-h-svh flex-col overflow-hidden bg-[#f7f9fc]">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[28rem] bg-[linear-gradient(180deg,rgba(35,106,85,0.14),rgba(213,150,52,0.08),transparent)] dark:bg-[linear-gradient(180deg,rgba(74,157,177,0.14),rgba(35,106,85,0.1),transparent)]"
        aria-hidden
      />

      <AppNavbar is_signed_in={is_signed_in} />

      <main className="relative z-10 mx-auto flex w-full max-w-[1200px] flex-1 flex-col px-5 py-12 sm:px-8 sm:py-16 lg:py-10">
        <section className="mx-auto max-w-[900px] text-center" aria-labelledby="home-heading">
          <h1
            id="home-heading"
            className="font-heading text-balance text-5xl font-bold leading-[1.03] tracking-[-0.045em] text-[#101a32] sm:text-7xl"
          >
            Trusted local guidance for
            <span className="block bg-gradient-to-r from-[#2864e8] to-[#24479c] bg-clip-text text-transparent">communities navigating</span>
            <span className="block bg-gradient-to-r from-[#2864e8] to-[#24479c] bg-clip-text text-transparent">conflict</span>
          </h1>
          <p className="mx-auto mt-10 max-w-[760px] text-pretty text-xl leading-[1.55] text-[#607694] sm:text-2xl">
            Ubuntu Voice turns curated peacebuilding and civil society knowledge into low-bandwidth AI
            support for displaced people, women, youth, and local organizations across Africa.
          </p>
          <div className="mt-14 flex flex-col items-center justify-center gap-4 sm:flex-row">
            {!is_signed_in ? (
              <>
              <Button size="lg" className="min-w-[260px] rounded-full bg-[#2864e8] px-9 text-lg text-white shadow-md hover:bg-[#1f56ce]" asChild>
                <Link href="/register">
                  Start with Ubuntu Voice
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
              </Button>
              <Button size="lg" variant="outline" className="min-w-[260px] rounded-full border-[#dce4ef] bg-white px-9 text-lg text-[#123f88]" asChild>
                <Link href="#mission">Explore mission</Link>
              </Button>
              </>
            ) : (
              <>
              <Button size="lg" className="min-w-[260px] rounded-full bg-[#2864e8] px-9 text-lg text-white shadow-md hover:bg-[#1f56ce]" asChild>
                <Link href="/chat">
                  Open community chat
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
              </Button>
              <Button size="lg" variant="outline" className="min-w-[260px] rounded-full border-[#dce4ef] bg-white px-9 text-lg text-[#123f88]" asChild>
                <Link href="/documents">Curate knowledge</Link>
              </Button>
              </>
            )}
          </div>
        </section>

        <section
          id="mission"
          className="mx-auto mt-16 grid max-w-5xl gap-4 sm:mt-20 sm:grid-cols-3"
          aria-labelledby="mission-heading"
        >
          <h2 id="mission-heading" className="sr-only">
            Ubuntu Voice mission pillars
          </h2>
          <div className="rounded-2xl border border-border/80 bg-card/70 p-5 shadow-sm">
            <UsersRound className="mb-3 size-5 text-primary" aria-hidden />
            <p className="text-sm font-semibold text-foreground">Community-defined agents</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Sahel Peace Mediator, DRC Women Peacebuilders, and Resource Rights Advisor style agents.
            </p>
          </div>
          <div className="rounded-2xl border border-border/80 bg-card/70 p-5 shadow-sm">
            <Radio className="mb-3 size-5 text-primary" aria-hidden />
            <p className="text-sm font-semibold text-foreground">Low-bandwidth by design</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Built for lightweight chat flows with SMS, USSD, WhatsApp, email, and voice-ready pathways.
            </p>
          </div>
          <div className="rounded-2xl border border-border/80 bg-card/70 p-5 shadow-sm">
            <Shield className="mb-3 size-5 text-primary" aria-hidden />
            <p className="text-sm font-semibold text-foreground">Safety and privacy first</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Minimizes personal data and keeps answers grounded in trusted local documents.
            </p>
          </div>
        </section>

        <section
          id="features"
          className="mx-auto mt-16 grid max-w-5xl gap-5 sm:mt-20 sm:grid-cols-2 lg:grid-cols-3 lg:gap-6"
          aria-labelledby="features-heading"
        >
          <h2 id="features-heading" className="sr-only">
            Platform capabilities
          </h2>
          {feature_card({
            icon: MessageSquare,
            title: "Real-time community support",
            description:
              "People can ask practical questions and receive concise, localized responses shaped by approved peacebuilding knowledge.",
          })}
          {feature_card({
            icon: FileText,
            title: "Grounded in trusted sources",
            description:
              "Civil society documents become active guidance, with clear fallback when there is not enough reliable information.",
          })}
          {feature_card({
            icon: Languages,
            title: "Inclusive language access",
            description:
              "The experience is designed for multilingual communities, including French, Swahili, and locally preferred languages.",
          })}
          {feature_card({
            icon: Globe2,
            title: "Built for African contexts",
            description:
              "Focused on communities in the Sahel, DRC, Sudan, Mozambique, and other conflict-affected regions.",
          })}
          {feature_card({
            icon: Shield,
            title: "Sensitive by default",
            description:
              "The platform avoids presenting AI output as legal, medical, security, or emergency advice.",
          })}
          {feature_card({
            icon: UsersRound,
            title: "Human escalation ready",
            description:
              "High-risk needs can be routed toward trusted local organizations, verified contacts, and safer next steps.",
          })}
        </section>
      </main>

      <footer className="relative z-10 border-t border-border/60 bg-muted/30 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 text-center text-xs text-muted-foreground sm:flex-row sm:px-6 sm:text-left lg:px-8">
          <p>{new Date().getFullYear()} Ubuntu Voice. Community peace support AI.</p>
          <p className="font-mono">Privacy-first RAG for locally led resilience.</p>
        </div>
      </footer>
    </div>
  )
}
