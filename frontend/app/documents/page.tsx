"use client"

import { UserButton } from "@clerk/nextjs"
import Link from "next/link"
import { useCallback, useEffect, useRef, useState } from "react"
import {
  ArrowLeft,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  File,
  FileCode,
  FileImage,
  FileJson,
  FileSpreadsheet,
  FileText,
  FileUp,
  FolderOpen,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Upload,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"
import { cn } from "@/lib/utils"

// ─── Types ────────────────────────────────────────────────────────────────────

type CompanyResponse = {
  id: string
  name: string
  email: string
  phone: string | null
  description: string | null
  owner_id: string
  created_at: string
}

type DocumentResponse = {
  id: string
  company_id: string
  uploaded_by: string
  file_name: string
  file_path: string
  file_size: number | null
  file_type: string | null
  status: "pending" | "processing" | "completed" | "failed" | string
  is_embedded: boolean
  created_at: string
}

type CompanyWithDocumentsResponse = {
  company: CompanyResponse
  documents: DocumentResponse[]
}

type QueuedFile = {
  id: string
  file: File
}

type UploadTicket = {
  document_id: string
  file_name: string
  file_path: string
  upload_url: string
  method: "PUT"
  content_type: string
}

type UploadsMintResponse = {
  mode: "direct" | "multipart"
  uploads: UploadTicket[]
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Builds a human-readable error string from common API JSON shapes.
 */
function format_error_payload(data: unknown): string {
  if (typeof data !== "object" || data === null) return "Request failed"
  const err = (data as { error?: unknown }).error
  if (typeof err === "string") return err
  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg)
        }
        return JSON.stringify(item)
      })
      .join("; ")
  }
  return "Request failed"
}

/**
 * Formats a byte length into a human-readable string.
 */
function format_file_size(bytes: number | null): string {
  if (bytes === null || Number.isNaN(bytes)) return "—"
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

/**
 * Formats an ISO timestamp for compact display.
 */
function format_short_date(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * Returns a Lucide icon component based on a MIME type string.
 */
function get_file_icon(mime: string | null): typeof File {
  if (!mime) return File
  if (mime.startsWith("image/")) return FileImage
  if (mime === "application/json") return FileJson
  if (mime === "text/csv" || mime.includes("spreadsheet") || mime.includes("excel")) return FileSpreadsheet
  if (mime.startsWith("text/") || mime.includes("pdf") || mime.includes("word")) return FileText
  if (mime.includes("javascript") || mime.includes("typescript") || mime.includes("html") || mime.includes("xml"))
    return FileCode
  return File
}

/**
 * Returns a colour class pair for a document status badge.
 */
function status_badge_class(s: string): string {
  if (s === "pending") return "bg-amber-500/15 text-amber-700 dark:text-amber-400"
  if (s === "processing") return "bg-sky-500/15 text-sky-700 dark:text-sky-400"
  if (s === "completed") return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
  if (s === "failed") return "bg-destructive/15 text-destructive"
  return "bg-muted text-muted-foreground"
}

/**
 * Derives a label and colour class for the embedding status badge.
 */
function embedding_badge(doc: DocumentResponse): { label: string; cls: string; spinning: boolean } | null {
  if (doc.is_embedded) {
    return { label: "Embedded", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400", spinning: false }
  }
  if (doc.status === "processing") {
    return { label: "Embedding…", cls: "bg-sky-500/15 text-sky-700 dark:text-sky-400", spinning: true }
  }
  if (doc.status === "failed") {
    return null
  }
  return { label: "Not embedded", cls: "bg-muted text-muted-foreground", spinning: false }
}

// ─── Sub-components ───────────────────────────────────────────────────────────

/**
 * Renders a single row in the staged-file queue with a remove button.
 */
function QueuedFileRow({
  entry,
  on_remove,
}: {
  entry: QueuedFile
  on_remove: (id: string) => void
}) {
  const Icon = get_file_icon(entry.file.type)
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/20 px-3 py-2">
      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="min-w-0 flex-1 truncate text-sm text-foreground">{entry.file.name}</span>
      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
        {format_file_size(entry.file.size)}
      </span>
      <button
        type="button"
        onClick={() => on_remove(entry.id)}
        className="ml-1 shrink-0 rounded p-0.5 text-muted-foreground hover:text-destructive"
        aria-label={`Remove ${entry.file.name}`}
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}

/**
 * Renders a single document card in the uploaded-documents grid.
 */
function DocumentCard({ doc, is_new }: { doc: DocumentResponse; is_new: boolean }) {
  const Icon = get_file_icon(doc.file_type)
  return (
    <div
      className={cn(
        "group relative flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm transition-colors",
        is_new ? "border-primary/40 bg-primary/5" : "border-border hover:border-border/80 hover:bg-muted/20",
      )}
    >
      {is_new && (
        <span className="absolute right-3 top-3 flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
          <CheckCircle2 className="size-2.5" aria-hidden />
          New
        </span>
      )}
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <Icon className="size-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1 pt-0.5">
          <p className="truncate text-sm font-medium text-foreground" title={doc.file_name}>
            {doc.file_name}
          </p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {doc.file_type ?? "unknown type"} · {format_file_size(doc.file_size)}
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium", status_badge_class(doc.status))}>
            {doc.status}
          </span>
          <span className="text-xs text-muted-foreground">{format_short_date(doc.created_at)}</span>
        </div>
        {(() => {
          const badge = embedding_badge(doc)
          if (!badge) return null
          return (
            <span className={cn("inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", badge.cls)}>
              {badge.spinning ? (
                <Loader2 className="size-2.5 animate-spin" aria-hidden />
              ) : (
                <BrainCircuit className="size-2.5" aria-hidden />
              )}
              {badge.label}
            </span>
          )
        })()}
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const [companies, set_companies] = useState<CompanyResponse[]>([])
  const [selected_company_id, set_selected_company_id] = useState<string | null>(null)
  const [documents, set_documents] = useState<DocumentResponse[]>([])
  const [new_doc_ids, set_new_doc_ids] = useState<Set<string>>(new Set())

  const [company_name, set_company_name] = useState("")
  const [company_email, set_company_email] = useState("")
  const [company_phone, set_company_phone] = useState("")
  const [company_description, set_company_description] = useState("")
  const [show_create_form, set_show_create_form] = useState(false)

  const [editing_company_id, set_editing_company_id] = useState<string | null>(null)
  const [edit_company_name, set_edit_company_name] = useState("")
  const [edit_company_email, set_edit_company_email] = useState("")
  const [edit_company_phone, set_edit_company_phone] = useState("")
  const [edit_company_description, set_edit_company_description] = useState("")

  const [queued_files, set_queued_files] = useState<QueuedFile[]>([])
  const [drag_active, set_drag_active] = useState(false)

  const [page_loading, set_page_loading] = useState(true)
  const [creating_company, set_creating_company] = useState(false)
  const [updating_company, set_updating_company] = useState(false)
  const [list_loading, set_list_loading] = useState(false)
  const [uploading, set_uploading] = useState(false)
  const [triggering_embed, set_triggering_embed] = useState(false)
  const [error, set_error] = useState<string | null>(null)

  const file_input_ref = useRef<HTMLInputElement | null>(null)

  // ── Data fetching ──────────────────────────────────────────────────────────

  const load_companies = useCallback(async () => {
    const res = await fetch("/api/ingestion/companies")
    const data: unknown = await res.json().catch(() => ({}))
    if (!res.ok) { set_error(format_error_payload(data)); return }
    if (!Array.isArray(data)) { set_error("Unexpected agents response"); return }
    const list = data as CompanyResponse[]
    set_companies(list)
    set_selected_company_id((prev) => {
      if (list.length === 0) return null
      if (prev && list.some((c) => c.id === prev)) return prev
      return list[0].id
    })
  }, [])

  const load_documents = useCallback(async (company_id: string) => {
    set_list_loading(true)
    try {
      const res = await fetch(`/api/ingestion/companies/${encodeURIComponent(company_id)}/documents`)
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) { set_error(format_error_payload(data)); set_documents([]); return }
      const parsed = data as Partial<CompanyWithDocumentsResponse>
      set_documents((parsed.documents as DocumentResponse[]) ?? [])
    } finally {
      set_list_loading(false)
    }
  }, [])

  const bootstrap = useCallback(async () => {
    set_page_loading(true)
    set_error(null)
    try {
      const reg = await fetch("/api/ingestion/register", { method: "POST" })
      const reg_data: unknown = await reg.json().catch(() => ({}))
      if (!reg.ok) { set_error(format_error_payload(reg_data)); return }
      await load_companies()
    } finally {
      set_page_loading(false)
    }
  }, [load_companies])

  useEffect(() => { void bootstrap() }, [bootstrap])

  useEffect(() => {
    if (!selected_company_id) { set_documents([]); return }
    void load_documents(selected_company_id)
  }, [selected_company_id, load_documents])

  // ── Agent creation ─────────────────────────────────────────────────────────

  const create_company = useCallback(async () => {
    const name = company_name.trim()
    const email = company_email.trim()
    const phone = company_phone.trim()
    const description = company_description.trim()
    if (!name || !email) return
    set_creating_company(true)
    set_error(null)
    try {
      const res = await fetch("/api/ingestion/companies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, ...(phone ? { phone } : {}), ...(description ? { description } : {}) }),
      })
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) { set_error(format_error_payload(data)); return }
      const created = data as Partial<CompanyResponse>
      if (!created.id) { set_error("Unexpected response"); return }
      set_company_name("")
      set_company_email("")
      set_company_phone("")
      set_company_description("")
      set_show_create_form(false)
      set_companies((prev) => (prev.some((c) => c.id === created.id) ? prev : [...prev, created as CompanyResponse]))
      set_selected_company_id(created.id)
    } finally {
      set_creating_company(false)
    }
  }, [company_description, company_name, company_email, company_phone])

  // ── Agent editing ──────────────────────────────────────────────────────────

  const cancel_edit_company = useCallback(() => {
    set_editing_company_id(null)
    set_edit_company_name("")
    set_edit_company_email("")
    set_edit_company_phone("")
    set_edit_company_description("")
  }, [])

  const begin_edit_company = useCallback((company: CompanyResponse) => {
    set_editing_company_id(company.id)
    set_edit_company_name(company.name)
    set_edit_company_email(company.email)
    set_edit_company_phone(company.phone ?? "")
    set_edit_company_description(company.description ?? "")
    set_selected_company_id(company.id)
    set_show_create_form(false)
    set_error(null)
  }, [])

  const update_company = useCallback(async () => {
    if (!editing_company_id) return
    const name = edit_company_name.trim()
    const email = edit_company_email.trim()
    const phone = edit_company_phone.trim()
    const description = edit_company_description.trim()
    if (!name || !email) return

    set_updating_company(true)
    set_error(null)
    try {
      const res = await fetch(`/api/ingestion/companies/${encodeURIComponent(editing_company_id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          phone: phone || null,
          description: description || null,
        }),
      })
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) { set_error(format_error_payload(data)); return }
      const updated = data as Partial<CompanyResponse>
      if (!updated.id) { set_error("Unexpected response"); return }
      set_companies((prev) => prev.map((c) => (c.id === updated.id ? (updated as CompanyResponse) : c)))
      set_selected_company_id(updated.id)
      cancel_edit_company()
    } finally {
      set_updating_company(false)
    }
  }, [
    cancel_edit_company,
    edit_company_description,
    edit_company_email,
    edit_company_name,
    edit_company_phone,
    editing_company_id,
  ])

  // ── File queue management ──────────────────────────────────────────────────

  const enqueue_files = useCallback((file_list: FileList | File[]) => {
    const pdf_only = Array.from(file_list).filter(
      (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"),
    )
    const incoming = pdf_only.map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}-${file.name}`,
      file,
    }))
    set_queued_files((prev) => {
      const existing_names = new Set(prev.map((e) => e.file.name))
      return [...prev, ...incoming.filter((e) => !existing_names.has(e.file.name))]
    })
  }, [])

  const remove_queued_file = useCallback((id: string) => {
    set_queued_files((prev) => prev.filter((e) => e.id !== id))
  }, [])

  // ── Upload ─────────────────────────────────────────────────────────────────

  /**
   * Legacy multipart upload, used when the backend signals mode="multipart"
   * (i.e. Supabase storage is not configured, e.g. local dev).
   */
  const upload_via_multipart = useCallback(
    async (company_id: string, entries: QueuedFile[]): Promise<DocumentResponse[] | null> => {
      const form = new FormData()
      for (const entry of entries) form.append("files", entry.file)
      const res = await fetch(
        `/api/ingestion/companies/${encodeURIComponent(company_id)}/documents`,
        { method: "POST", body: form },
      )
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) {
        set_error(format_error_payload(data))
        return null
      }
      return (Array.isArray(data) ? data : []) as DocumentResponse[]
    },
    [],
  )

  /**
   * Direct-to-Supabase upload via signed URLs. Bypasses the backend entirely
   * for the file bytes, so free-tier hosts cannot become a transfer bottleneck.
   */
  const upload_via_signed_urls = useCallback(
    async (
      company_id: string,
      entries: QueuedFile[],
      tickets: UploadTicket[],
    ): Promise<DocumentResponse[] | null> => {
      const ticket_by_name = new Map(tickets.map((t) => [t.file_name, t]))
      for (const entry of entries) {
        const ticket = ticket_by_name.get(entry.file.name)
        if (!ticket) {
          set_error(`No upload ticket for ${entry.file.name}`)
          return null
        }
        let put_response: Response
        try {
          put_response = await fetch(ticket.upload_url, {
            method: ticket.method,
            headers: { "Content-Type": ticket.content_type },
            body: entry.file,
          })
        } catch (err) {
          const msg = err instanceof Error ? err.message : "network error"
          set_error(`Upload of ${entry.file.name} failed: ${msg}`)
          return null
        }
        if (!put_response.ok) {
          const body = await put_response.text().catch(() => "")
          set_error(`Upload of ${entry.file.name} failed (${put_response.status}): ${body.slice(0, 200)}`)
          return null
        }
      }

      const confirm_payload = {
        documents: tickets.map((t) => ({
          document_id: t.document_id,
          file_path: t.file_path,
          file_name: t.file_name,
          content_type: t.content_type,
        })),
      }
      const confirm_res = await fetch(
        `/api/ingestion/companies/${encodeURIComponent(company_id)}/documents/confirm`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(confirm_payload),
        },
      )
      const confirm_data: unknown = await confirm_res.json().catch(() => ({}))
      if (!confirm_res.ok) {
        set_error(format_error_payload(confirm_data))
        return null
      }
      return (Array.isArray(confirm_data) ? confirm_data : []) as DocumentResponse[]
    },
    [],
  )

  const upload_queued = useCallback(async () => {
    if (!selected_company_id || queued_files.length === 0) return
    set_uploading(true)
    set_error(null)
    try {
      const file_meta = {
        files: queued_files.map((entry) => ({
          file_name: entry.file.name,
          file_size: entry.file.size,
          content_type: entry.file.type || "application/pdf",
        })),
      }
      const mint_res = await fetch(
        `/api/ingestion/companies/${encodeURIComponent(selected_company_id)}/documents/uploads`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(file_meta),
        },
      )
      const mint_data: unknown = await mint_res.json().catch(() => ({}))
      if (!mint_res.ok) {
        set_error(format_error_payload(mint_data))
        return
      }
      const mint_parsed = mint_data as Partial<UploadsMintResponse>

      let uploaded: DocumentResponse[] | null
      if (mint_parsed.mode === "direct" && Array.isArray(mint_parsed.uploads)) {
        uploaded = await upload_via_signed_urls(selected_company_id, queued_files, mint_parsed.uploads)
      } else {
        uploaded = await upload_via_multipart(selected_company_id, queued_files)
      }
      if (!uploaded) return

      const ids = new Set(uploaded.map((d) => d.id))
      set_new_doc_ids(ids)
      setTimeout(() => set_new_doc_ids(new Set()), 6000)
      set_queued_files([])
      await load_documents(selected_company_id)
    } finally {
      set_uploading(false)
    }
  }, [
    selected_company_id,
    queued_files,
    load_documents,
    upload_via_signed_urls,
    upload_via_multipart,
  ])

  // ── Embed ──────────────────────────────────────────────────────────────────

  const trigger_embed = useCallback(async () => {
    if (!selected_company_id) return
    set_triggering_embed(true)
    set_error(null)
    try {
      const res = await fetch(
        `/api/ingestion/companies/${encodeURIComponent(selected_company_id)}/embed`,
        { method: "POST" },
      )
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) { set_error(format_error_payload(data)); return }
      await load_documents(selected_company_id)
    } finally {
      set_triggering_embed(false)
    }
  }, [selected_company_id, load_documents])

  const can_create_company =
    company_name.trim().length > 0 && company_email.trim().length > 0
  const description_length = company_description.length
  const can_update_company =
    Boolean(editing_company_id) &&
    edit_company_name.trim().length > 0 &&
    edit_company_email.trim().length > 0
  const edit_description_length = edit_company_description.length
  const selected_company = companies.find((c) => c.id === selected_company_id)

  return (
    <div className="flex min-h-svh flex-col bg-background">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/90 px-4 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-3">
          <Button variant="ghost" size="icon-sm" asChild>
            <Link href="/" aria-label="Back to home"><ArrowLeft /></Link>
          </Button>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm font-semibold text-foreground">Agent knowledge</h1>
          </div>
          <Button variant="outline" size="sm" className="hidden sm:inline-flex" asChild>
            <Link href="/chat">Chat</Link>
          </Button>
          <ThemeToggle />
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        {page_loading ? (
          <div className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
            <Loader2 className="size-8 animate-spin text-primary" />
            <p className="text-sm">Loading agents...</p>
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[280px_1fr]">

            {/* ── Left column: agent panel ── */}
            <aside className="flex flex-col gap-4">
              <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    <BrainCircuit className="size-3.5" />
                    Agents
                  </h2>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => void bootstrap()}
                    title="Refresh"
                  >
                    <RefreshCw className="size-3.5" />
                  </Button>
                </div>

                {/* Agent list */}
                <div className="mt-3 flex flex-col gap-1">
                  {companies.length === 0 ? (
                    <p className="py-3 text-center text-xs text-muted-foreground">No agents yet.</p>
                  ) : (
                    companies.map((c) => (
                      <div
                        key={c.id}
                        className={cn(
                          "flex w-full items-start gap-1 rounded-lg pr-1 transition-colors",
                          c.id === selected_company_id
                            ? "bg-primary/10"
                            : "hover:bg-muted",
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => set_selected_company_id(c.id)}
                          className={cn(
                            "min-w-0 flex-1 px-3 py-2 text-left text-sm",
                            c.id === selected_company_id ? "text-primary" : "text-foreground",
                          )}
                        >
                          <span className="block truncate font-medium leading-tight">{c.name}</span>
                          <span className="block truncate text-xs text-muted-foreground">{c.email}</span>
                          {c.phone ? <span className="block truncate text-xs text-muted-foreground">{c.phone}</span> : null}
                          {c.description ? (
                            <span className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                              {c.description}
                            </span>
                          ) : null}
                        </button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          className="mt-1.5"
                          onClick={() => begin_edit_company(c)}
                          title={`Edit ${c.name}`}
                        >
                          <Pencil className="size-3" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>

                {editing_company_id && (
                  <div className="mt-3 border-t border-border pt-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <p className="text-xs font-medium text-foreground">Edit agent</p>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        onClick={cancel_edit_company}
                        title="Cancel edit"
                      >
                        <X className="size-3" />
                      </Button>
                    </div>
                    <div className="flex flex-col gap-2">
                      <input
                        value={edit_company_name}
                        onChange={(e) => set_edit_company_name(e.target.value)}
                        placeholder="Agent name"
                        className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring"
                      />
                      <input
                        type="email"
                        value={edit_company_email}
                        onChange={(e) => set_edit_company_email(e.target.value)}
                        placeholder="agent-contact@example.org"
                        className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring"
                      />
                      <input
                        type="tel"
                        value={edit_company_phone}
                        onChange={(e) => set_edit_company_phone(e.target.value)}
                        placeholder="+254712345678 (optional)"
                        className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring"
                      />
                      <div>
                        <textarea
                          value={edit_company_description}
                          maxLength={300}
                          rows={4}
                          onChange={(e) => set_edit_company_description(e.target.value)}
                          placeholder="Agent purpose, audience, or document focus (optional)"
                          className="min-h-24 w-full resize-none rounded-lg border border-input bg-background px-2.5 py-2 text-sm outline-none focus-visible:border-ring"
                        />
                        <p className="mt-1 text-right text-[11px] text-muted-foreground">
                          {edit_description_length}/300
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        className="w-full gap-1.5"
                        disabled={!can_update_company || updating_company}
                        onClick={() => void update_company()}
                      >
                        {updating_company ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <Save className="size-3.5" />
                        )}
                        Save changes
                      </Button>
                    </div>
                  </div>
                )}

                {/* New agent toggle */}
                <button
                  type="button"
                  onClick={() => {
                    cancel_edit_company()
                    set_show_create_form((v) => !v)
                  }}
                  className="mt-3 flex w-full items-center gap-1.5 rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
                >
                  <Plus className="size-3.5" />
                  New agent
                  <ChevronDown
                    className={cn("ml-auto size-3.5 transition-transform", show_create_form && "rotate-180")}
                  />
                </button>

                {show_create_form && (
                  <div className="mt-3 flex flex-col gap-2">
                    <input
                      value={company_name}
                      onChange={(e) => set_company_name(e.target.value)}
                      placeholder="Agent name"
                      className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring"
                    />
                    <input
                      type="email"
                      value={company_email}
                      onChange={(e) => set_company_email(e.target.value)}
                      placeholder="agent-contact@example.org"
                      className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring"
                    />
                    <input
                      type="tel"
                      value={company_phone}
                      onChange={(e) => set_company_phone(e.target.value)}
                      placeholder="+254712345678 (optional)"
                      className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring"
                    />
                    <div>
                      <textarea
                        value={company_description}
                        maxLength={300}
                        rows={4}
                        onChange={(e) => set_company_description(e.target.value)}
                        placeholder="Agent purpose, audience, or document focus (optional)"
                        className="min-h-24 w-full resize-none rounded-lg border border-input bg-background px-2.5 py-2 text-sm outline-none focus-visible:border-ring"
                      />
                      <p className="mt-1 text-right text-[11px] text-muted-foreground">
                        {description_length}/300
                      </p>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      className="w-full"
                      disabled={!can_create_company || creating_company}
                      onClick={() => void create_company()}
                    >
                      {creating_company ? <Loader2 className="size-3.5 animate-spin" /> : "Create agent"}
                    </Button>
                  </div>
                )}
              </div>
            </aside>

            {/* ── Right column: upload + document list ── */}
            <div className="flex flex-col gap-6">

              {/* Upload panel */}
              <section className="rounded-xl border border-border bg-card shadow-sm">
                <div className="border-b border-border px-5 py-3.5">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Upload className="size-4 text-primary" />
                    Upload documents
                  </h2>
                  {selected_company && (
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      <p>
                        Uploading to <span className="font-medium text-foreground">{selected_company.name}</span>
                      </p>
                      {selected_company.description ? (
                        <p className="mt-1 leading-relaxed">{selected_company.description}</p>
                      ) : null}
                    </div>
                  )}
                </div>

                <div className="p-5">
                  {/* Hidden file input */}
                  <input
                    ref={file_input_ref}
                    type="file"
                    multiple
                    accept=".pdf,application/pdf"
                    className="sr-only"
                    onChange={(e) => {
                      if (e.target.files) enqueue_files(e.target.files)
                      if (file_input_ref.current) file_input_ref.current.value = ""
                    }}
                    disabled={!selected_company_id}
                  />

                  {/* Drop zone */}
                  <button
                    type="button"
                    disabled={!selected_company_id}
                    onClick={() => file_input_ref.current?.click()}
                    onDragEnter={(e) => { e.preventDefault(); set_drag_active(true) }}
                    onDragOver={(e) => { e.preventDefault(); set_drag_active(true) }}
                    onDragLeave={(e) => { e.preventDefault(); set_drag_active(false) }}
                    onDrop={(e) => {
                      e.preventDefault()
                      set_drag_active(false)
                      if (!selected_company_id) return
                      if (e.dataTransfer.files?.length) enqueue_files(e.dataTransfer.files)
                    }}
                    className={cn(
                      "flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed py-8 text-center transition-all",
                      drag_active ? "border-primary bg-primary/5 scale-[1.01]" : "border-border bg-muted/10",
                      "hover:border-primary/50 hover:bg-muted/20",
                      "disabled:pointer-events-none disabled:opacity-40",
                    )}
                  >
                    <div className="flex size-12 items-center justify-center rounded-xl bg-muted">
                      <FileUp className="size-5 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {drag_active ? "Drop to add files" : "Drop files or click to browse"}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {selected_company_id
                          ? "Trusted PDFs for this agent corpus"
                          : "Select an agent on the left first"}
                      </p>
                    </div>
                  </button>

                  {/* Queued files list */}
                  {queued_files.length > 0 && (
                    <div className="mt-4 flex flex-col gap-2">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-medium text-muted-foreground">
                          {queued_files.length} file{queued_files.length !== 1 ? "s" : ""} ready to upload
                        </p>
                        <button
                          type="button"
                          onClick={() => set_queued_files([])}
                          className="text-xs text-muted-foreground hover:text-destructive"
                        >
                          Clear all
                        </button>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        {queued_files.map((entry) => (
                          <QueuedFileRow key={entry.id} entry={entry} on_remove={remove_queued_file} />
                        ))}
                      </div>
                      <Button
                        type="button"
                        className="mt-1 w-full gap-2"
                        disabled={uploading || !selected_company_id}
                        onClick={() => void upload_queued()}
                      >
                        {uploading ? (
                          <>
                            <Loader2 className="size-4 animate-spin" />
                            Uploading…
                          </>
                        ) : (
                          <>
                            <Upload className="size-4" />
                            Upload {queued_files.length} file{queued_files.length !== 1 ? "s" : ""}
                          </>
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              </section>

              {/* Documents section */}
              <section>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <FolderOpen className="size-4 text-primary" />
                    Uploaded documents
                    {documents.length > 0 && (
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                        {documents.length}
                      </span>
                    )}
                  </h2>
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="gap-1.5 text-xs text-muted-foreground"
                      disabled={!selected_company_id || triggering_embed}
                      onClick={() => selected_company_id && void trigger_embed()}
                    >
                      {triggering_embed ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <BrainCircuit className="size-3.5" />
                      )}
                      Embed pending
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="gap-1.5 text-xs text-muted-foreground"
                      disabled={!selected_company_id || list_loading}
                      onClick={() => selected_company_id && void load_documents(selected_company_id)}
                    >
                      {list_loading ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="size-3.5" />
                      )}
                      Refresh
                    </Button>
                  </div>
                </div>

                {!selected_company_id ? (
                  <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-16 text-muted-foreground">
                    <BrainCircuit className="size-8 opacity-30" />
                    <p className="text-sm">Select an agent to see its documents.</p>
                  </div>
                ) : list_loading && documents.length === 0 ? (
                  <div className="flex justify-center py-12">
                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                  </div>
                ) : documents.length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border py-16 text-muted-foreground">
                    <FolderOpen className="size-8 opacity-30" />
                    <p className="text-sm">No documents yet. Upload some above.</p>
                  </div>
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {documents.map((doc) => (
                      <DocumentCard key={doc.id} doc={doc} is_new={new_doc_ids.has(doc.id)} />
                    ))}
                  </div>
                )}
              </section>

              {/* Error banner */}
              {error && (
                <div
                  role="alert"
                  className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                >
                  <span className="flex-1">{error}</span>
                  <button type="button" onClick={() => set_error(null)} className="shrink-0 opacity-70 hover:opacity-100">
                    <X className="size-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
