"use client"

import { CheckCircle2, ChevronDown, ChevronUp, Loader2, Play, Plus, Trash2, XCircle } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { DashboardShell } from "@/components/dashboard-shell"
import { Button } from "@/components/ui/button"

type Company = { id: string; name: string }
type Question = { id: string; question: string; reference_answer: string; created_at: string }
type GradeKey = "correctness" | "relevance" | "groundedness" | "retrieval_relevance"
type Result = {
  id: string
  question: string
  reference_answer: string
  generated_answer: string
  retrieved_sources: { source: string; similarity: number }[]
  correctness_passed: boolean | null
  correctness_explanation: string | null
  relevance_passed: boolean | null
  relevance_explanation: string | null
  groundedness_passed: boolean | null
  groundedness_explanation: string | null
  retrieval_relevance_passed: boolean | null
  retrieval_relevance_explanation: string | null
  operational_error: string | null
}
type Run = {
  id: string
  status: "pending" | "running" | "completed" | "partial" | "failed"
  total_questions: number
  completed_questions: number
  error_message: string | null
  results: Result[]
}
type Workspace = { questions: Question[]; latest_run: Run | null }

const grade_labels: Record<GradeKey, string> = {
  correctness: "Correctness",
  relevance: "Relevance",
  groundedness: "Groundedness",
  retrieval_relevance: "Retrieval relevance",
}

// Extracts a readable API error message.
function error_message(data: unknown): string {
  if (typeof data !== "object" || data === null) return "Request failed."
  const detail = (data as { detail?: unknown }).detail
  const error = (data as { error?: unknown }).error
  return typeof detail === "string" ? detail : typeof error === "string" ? error : "Request failed."
}

// Displays a pass, fail, or unavailable grade badge.
function GradeBadge({ value }: { value: boolean | null }) {
  if (value === null) return <span className="rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">Unavailable</span>
  return value ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-1 text-xs text-emerald-700 dark:text-emerald-400"><CheckCircle2 className="size-3" />Pass</span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-destructive/15 px-2 py-1 text-xs text-destructive"><XCircle className="size-3" />Fail</span>
  )
}

export default function EvaluationsPage() {
  const [companies, set_companies] = useState<Company[]>([])
  const [company_id, set_company_id] = useState("")
  const [workspace, set_workspace] = useState<Workspace | null>(null)
  const [question, set_question] = useState("")
  const [reference_answer, set_reference_answer] = useState("")
  const [expanded, set_expanded] = useState<Set<string>>(new Set())
  const [dataset_expanded, set_dataset_expanded] = useState(false)
  const [loading, set_loading] = useState(true)
  const [saving, set_saving] = useState(false)
  const [error, set_error] = useState<string | null>(null)

  const load_workspace = useCallback(async (selected_id: string, quiet = false) => {
    if (!quiet) set_loading(true)
    try {
      const response = await fetch(`/api/evaluations/${selected_id}`, { cache: "no-store" })
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(error_message(data))
      set_workspace(data as Workspace)
    } catch (caught) {
      set_error(caught instanceof Error ? caught.message : "Unable to load evaluations.")
    } finally {
      if (!quiet) set_loading(false)
    }
  }, [])

  useEffect(() => {
    const timeout_id = window.setTimeout(async () => {
      try {
        const response = await fetch("/api/ingestion/companies")
        const data: unknown = await response.json().catch(() => [])
        if (!response.ok || !Array.isArray(data)) throw new Error(error_message(data))
        const available = data as Company[]
        set_companies(available)
        if (available[0]) set_company_id(available[0].id)
        else set_loading(false)
      } catch (caught) {
        set_error(caught instanceof Error ? caught.message : "Unable to load agents.")
        set_loading(false)
      }
    }, 0)
    return () => window.clearTimeout(timeout_id)
  }, [])

  useEffect(() => {
    if (!company_id) return
    const timeout_id = window.setTimeout(() => void load_workspace(company_id), 0)
    return () => window.clearTimeout(timeout_id)
  }, [company_id, load_workspace])

  const is_running = workspace?.latest_run?.status === "pending" || workspace?.latest_run?.status === "running"
  useEffect(() => {
    if (!company_id || !is_running) return
    const interval_id = window.setInterval(() => void load_workspace(company_id, true), 2500)
    return () => window.clearInterval(interval_id)
  }, [company_id, is_running, load_workspace])

  const summary = useMemo(() => {
    const results = workspace?.latest_run?.results ?? []
    return (Object.keys(grade_labels) as GradeKey[]).map((key) => ({
      key,
      passed: results.filter((result) => result[`${key}_passed`] === true).length,
      total: results.filter((result) => result[`${key}_passed`] !== null).length,
    }))
  }, [workspace])

  async function add_question() {
    if (!company_id || !question.trim() || !reference_answer.trim()) return
    set_saving(true)
    set_error(null)
    try {
      const response = await fetch(`/api/evaluations/${company_id}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, reference_answer }),
      })
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(error_message(data))
      set_question("")
      set_reference_answer("")
      await load_workspace(company_id, true)
    } catch (caught) {
      set_error(caught instanceof Error ? caught.message : "Unable to add question.")
    } finally {
      set_saving(false)
    }
  }

  async function remove_question(question_id: string) {
    set_saving(true)
    try {
      const response = await fetch(`/api/evaluations/${company_id}/questions/${question_id}`, { method: "DELETE" })
      if (!response.ok) throw new Error(error_message(await response.json().catch(() => ({}))))
      await load_workspace(company_id, true)
    } catch (caught) {
      set_error(caught instanceof Error ? caught.message : "Unable to delete question.")
    } finally {
      set_saving(false)
    }
  }

  async function run_evaluation() {
    set_saving(true)
    set_error(null)
    try {
      const response = await fetch(`/api/evaluations/${company_id}/runs`, { method: "POST" })
      const data: unknown = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(error_message(data))
      await load_workspace(company_id, true)
    } catch (caught) {
      set_error(caught instanceof Error ? caught.message : "Unable to start evaluation.")
    } finally {
      set_saving(false)
    }
  }

  // Toggles one question result's expanded detail panel.
  function toggle_result(result_id: string) {
    set_expanded((current) => {
      const next = new Set(current)
      if (next.has(result_id)) {
        next.delete(result_id)
      } else {
        next.add(result_id)
      }
      return next
    })
  }

  return (
    <DashboardShell title="Evaluations" description="Run independent RAG quality checks against an agent's test dataset.">
      <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm font-medium text-foreground">
            Agent
            <select value={company_id} onChange={(event) => set_company_id(event.target.value)} className="mt-2 h-9 w-full rounded-lg border border-border bg-background px-3">
              {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
            </select>
          </label>
          <Button onClick={() => void run_evaluation()} disabled={!company_id || !workspace?.questions.length || is_running || saving}>
            {is_running ? <Loader2 className="animate-spin" /> : <Play />} {is_running ? "Running..." : "Run evaluation"}
          </Button>
        </div>
        {is_running && workspace?.latest_run ? (
          <p className="mt-3 text-sm text-muted-foreground">Completed {workspace.latest_run.completed_questions} of {workspace.latest_run.total_questions} questions.</p>
        ) : null}
        {workspace?.latest_run ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Latest run status: <span className="font-medium capitalize text-foreground">{workspace.latest_run.status}</span>
            {workspace.latest_run.error_message ? ` - ${workspace.latest_run.error_message}` : ""}
          </p>
        ) : null}
      </section>

      {error ? <div className="mt-5 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

      <section className="mt-6 space-y-5">
        <div className="rounded-xl border border-border bg-card shadow-sm">
          <button
            type="button"
            className="flex w-full items-center gap-3 px-5 py-4 text-left"
            onClick={() => set_dataset_expanded((current) => !current)}
            aria-expanded={dataset_expanded}
          >
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold">Test dataset</h2>
              <p className="text-xs text-muted-foreground">{workspace?.questions.length ?? 0} of 50 questions</p>
            </div>
            {dataset_expanded ? <ChevronUp /> : <ChevronDown />}
          </button>

          {dataset_expanded ? (
            <div className="border-t border-border">
              <div className="grid gap-3 p-5 md:grid-cols-2">
                <textarea value={question} onChange={(event) => set_question(event.target.value)} placeholder="Question" className="min-h-32 w-full rounded-lg border border-border bg-background p-3 text-sm" disabled={is_running} />
                <textarea value={reference_answer} onChange={(event) => set_reference_answer(event.target.value)} placeholder="Reference answer" className="min-h-32 w-full rounded-lg border border-border bg-background p-3 text-sm" disabled={is_running} />
                <div className="md:col-span-2">
                  <Button onClick={() => void add_question()} disabled={saving || is_running || !question.trim() || !reference_answer.trim()}><Plus />Add question</Button>
                </div>
              </div>
              <div className="max-h-[30rem] divide-y divide-border overflow-y-auto border-t border-border">
                {workspace?.questions.map((item) => (
                  <div key={item.id} className="flex gap-3 p-5">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground">{item.question}</p>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{item.reference_answer}</p>
                    </div>
                    <Button variant="ghost" size="icon-sm" aria-label="Delete question" disabled={saving || is_running} onClick={() => void remove_question(item.id)}><Trash2 /></Button>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-5">
          {workspace?.latest_run ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {summary.map((item) => <div key={item.key} className="rounded-xl border border-border bg-card p-4 shadow-sm"><p className="text-xs text-muted-foreground">{grade_labels[item.key]}</p><p className="mt-2 text-xl font-semibold">{item.passed}/{item.total}</p></div>)}
              </div>
              {workspace.latest_run.results.map((result) => {
                const is_expanded = expanded.has(result.id)
                return (
                  <article key={result.id} className="rounded-xl border border-border bg-card shadow-sm">
                    <button type="button" className="flex w-full items-start gap-3 p-5 text-left" onClick={() => toggle_result(result.id)}>
                      <div className="min-w-0 flex-1"><h3 className="font-medium text-foreground">{result.question}</h3><div className="mt-3 flex flex-wrap gap-2">{(Object.keys(grade_labels) as GradeKey[]).map((key) => <span key={key} className="inline-flex items-center gap-1 text-xs text-muted-foreground">{grade_labels[key]} <GradeBadge value={result[`${key}_passed`]} /></span>)}</div></div>
                      {is_expanded ? <ChevronUp /> : <ChevronDown />}
                    </button>
                    {is_expanded ? (
                      <div className="space-y-5 border-t border-border p-5 text-sm">
                        <div><h4 className="font-medium">Reference answer</h4><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{result.reference_answer}</p></div>
                        <div><h4 className="font-medium">Generated answer</h4><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{result.generated_answer || "Unavailable"}</p></div>
                        <div><h4 className="font-medium">Retrieved sources</h4><div className="mt-2 flex flex-wrap gap-2">{result.retrieved_sources.length ? result.retrieved_sources.map((source, index) => <span key={`${source.source}-${index}`} className="rounded-full bg-muted px-2 py-1 text-xs">{source.source} ({source.similarity.toFixed(3)})</span>) : <span className="text-muted-foreground">No sources retrieved.</span>}</div></div>
                        {(Object.keys(grade_labels) as GradeKey[]).map((key) => <div key={key} className="rounded-lg bg-muted/40 p-3"><div className="flex items-center justify-between"><h4 className="font-medium">{grade_labels[key]}</h4><GradeBadge value={result[`${key}_passed`]} /></div><p className="mt-2 text-muted-foreground">{result[`${key}_explanation`] ?? "No explanation available."}</p></div>)}
                        {result.operational_error ? <p className="text-destructive">{result.operational_error}</p> : null}
                      </div>
                    ) : null}
                  </article>
                )
              })}
            </>
          ) : loading ? <div className="flex justify-center py-16"><Loader2 className="animate-spin text-muted-foreground" /></div> : <div className="rounded-xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">Add questions and run the first evaluation.</div>}
        </div>
      </section>
    </DashboardShell>
  )
}
