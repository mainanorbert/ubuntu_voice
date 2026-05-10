import Image from "next/image"
import Link from "next/link"
import { SignInButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs"
import {
  ArrowRight,
  FileText,
  Globe2,
  Languages,
  MessageSquare,
  Radio,
  Shield,
  Sparkles,
  UsersRound,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"
import { cn } from "@/lib/utils"

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

export default function Page() {
  return (
    <div className="relative flex min-h-svh flex-col overflow-hidden bg-background">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[28rem] bg-[linear-gradient(180deg,rgba(35,106,85,0.14),rgba(213,150,52,0.08),transparent)] dark:bg-[linear-gradient(180deg,rgba(74,157,177,0.14),rgba(35,106,85,0.1),transparent)]"
        aria-hidden
      />

      <header className="relative z-10 border-b border-border/60 bg-background/82 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex min-w-0 items-center gap-3 transition-opacity hover:opacity-90">
            <Image
              src="/ub_voice.png"
              alt="Ubuntu Voice"
              width={200}
              height={52}
              className="h-9 w-auto max-w-[min(200px,42vw)] object-contain object-left sm:h-10"
              priority
            />
            <span className="hidden font-heading text-sm font-semibold tracking-tight text-foreground sm:inline">
              Peace support
            </span>
          </Link>
          <nav className="flex shrink-0 items-center gap-1 sm:gap-2">
            <ThemeToggle />
            <SignedOut>
              <SignInButton mode="modal">
                <Button size="sm" variant="outline">
                  Sign in
                </Button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <Button size="sm" className="hidden sm:inline-flex" asChild>
                <Link href="/chat">Community chat</Link>
              </Button>
              <Button size="sm" variant="outline" className="hidden sm:inline-flex" asChild>
                <Link href="/documents">Create agent</Link>
              </Button>
              <UserButton
                afterSignOutUrl="/"
                appearance={{
                  elements: { userButtonAvatarBox: "size-9 ring-2 ring-border/80" },
                }}
              />
            </SignedIn>
          </nav>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-14 sm:px-6 sm:py-20 lg:px-8 lg:py-24">
        <section className="mx-auto max-w-4xl text-center" aria-labelledby="home-heading">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-sm">
            <Sparkles className="size-3.5 text-primary" aria-hidden />
            Privacy-first community peace support
          </p>
          <h1
            id="home-heading"
            className="font-heading text-balance text-4xl font-semibold tracking-tight text-foreground sm:text-5xl sm:leading-[1.1]"
          >
            Trusted local guidance for communities navigating conflict
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
            Ubuntu Voice turns curated peacebuilding and civil society knowledge into low-bandwidth AI
            support for displaced people, women, youth, and local organizations across Africa.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-4">
            <SignedOut>
              <SignInButton mode="modal">
                <Button size="lg" className="min-w-[210px] gap-2 px-8 shadow-md">
                  Start with Ubuntu Voice
                  <ArrowRight className="size-4" aria-hidden />
                </Button>
              </SignInButton>
              <Button size="lg" variant="outline" className="min-w-[210px]" asChild>
                <Link href="#mission">Explore mission</Link>
              </Button>
            </SignedOut>
            <SignedIn>
              <Button size="lg" className="min-w-[220px] gap-2 px-8 shadow-md" asChild>
                <Link href="/chat">
                  Open community chat
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
              </Button>
              <Button size="lg" variant="outline" className="min-w-[220px]" asChild>
                <Link href="/documents">Curate knowledge</Link>
              </Button>
            </SignedIn>
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
