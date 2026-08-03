"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  BrainCircuit,
  FileText,
  FolderOpen,
  Loader2,
  Plus,
  RefreshCw,
  Upload,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { AppNavbar } from "@/components/app-navbar"

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
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/20 px-3 py-2">
      <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="min-w-0 flex-1 truncate text-sm text-foreground">
        {entry.file.name}
      </span>
      <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
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

/** Renders a document row for the selected agent. */
function DocumentCard({
  doc,
  is_new,
}: {
  doc: DocumentResponse
  is_new: boolean
}) {
  const is_embedded = doc.is_embedded
  const status = is_embedded
    ? "embedded"
    : doc.status === "processing"
      ? "embedding"
      : "pending"
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-4 border-b border-[#edf1f6] px-4 py-4 last:border-b-0 sm:px-5",
        is_new && "bg-[#f3f7ff]"
      )}
    >
      <div className="min-w-0">
        <p
          className="truncate font-serif text-[17px] leading-tight text-[#061b3b]"
          title={doc.file_name}
        >
          {doc.file_name}
        </p>
        <p className="mt-1 text-sm text-[#8aa0bd]">
          {format_file_size(doc.file_size)} · uploaded{" "}
          {format_short_date(doc.created_at)}
        </p>
      </div>
      <span
        className={cn(
          "shrink-0 rounded-full px-3 py-1 text-sm",
          is_embedded
            ? "bg-[#dff5ee] text-[#00806a]"
            : "bg-[#fdf0d9] text-[#a25800]"
        )}
      >
        {status}
      </span>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const [companies, set_companies] = useState<CompanyResponse[]>([])
  const [selected_company_id, set_selected_company_id] = useState<
    string | null
  >(null)
  const [documents, set_documents] = useState<DocumentResponse[]>([])
  const [new_doc_ids, set_new_doc_ids] = useState<Set<string>>(new Set())

  const [company_name, set_company_name] = useState("")
  const [company_email, set_company_email] = useState("")
  const [company_phone, set_company_phone] = useState("")
  const [company_description, set_company_description] = useState("")
  const [show_create_form, set_show_create_form] = useState(false)

  const [queued_files, set_queued_files] = useState<QueuedFile[]>([])
  const [pending_upload_company_id, set_pending_upload_company_id] = useState<
    string | null
  >(null)
  const [drag_active, set_drag_active] = useState(false)

  const [page_loading, set_page_loading] = useState(true)
  const [creating_company, set_creating_company] = useState(false)
  const [list_loading, set_list_loading] = useState(false)
  const [uploading, set_uploading] = useState(false)
  const [triggering_embed, set_triggering_embed] = useState(false)
  const [error, set_error] = useState<string | null>(null)

  const file_input_ref = useRef<HTMLInputElement | null>(null)

  // ── Data fetching ──────────────────────────────────────────────────────────

  const load_companies = useCallback(async () => {
    const res = await fetch("/api/ingestion/companies")
    const data: unknown = await res.json().catch(() => ({}))
    if (!res.ok) {
      set_error(format_error_payload(data))
      return
    }
    if (!Array.isArray(data)) {
      set_error("Unexpected agents response")
      return
    }
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
      const res = await fetch(
        `/api/ingestion/companies/${encodeURIComponent(company_id)}/documents`
      )
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) {
        set_error(format_error_payload(data))
        set_documents([])
        return
      }
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
      if (!reg.ok) {
        set_error(format_error_payload(reg_data))
        return
      }
      await load_companies()
    } finally {
      set_page_loading(false)
    }
  }, [load_companies])

  useEffect(() => {
    void Promise.resolve().then(bootstrap)
  }, [bootstrap])

  useEffect(() => {
    if (!selected_company_id) return
    void Promise.resolve().then(() => load_documents(selected_company_id))
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
        body: JSON.stringify({
          name,
          email,
          ...(phone ? { phone } : {}),
          ...(description ? { description } : {}),
        }),
      })
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) {
        set_error(format_error_payload(data))
        return
      }
      const created = data as Partial<CompanyResponse>
      if (!created.id) {
        set_error("Unexpected response")
        return
      }
      set_company_name("")
      set_company_email("")
      set_company_phone("")
      set_company_description("")
      set_show_create_form(false)
      set_companies((prev) =>
        prev.some((c) => c.id === created.id)
          ? prev
          : [...prev, created as CompanyResponse]
      )
      set_selected_company_id(created.id)
      if (queued_files.length > 0) set_pending_upload_company_id(created.id)
    } finally {
      set_creating_company(false)
    }
  }, [
    company_description,
    company_name,
    company_email,
    company_phone,
    queued_files.length,
  ])

  // ── File queue management ──────────────────────────────────────────────────

  const enqueue_files = useCallback((file_list: FileList | File[]) => {
    const pdf_only = Array.from(file_list).filter(
      (f) =>
        f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
    )
    const incoming = pdf_only.map((file) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}-${file.name}`,
      file,
    }))
    set_queued_files((prev) => {
      const existing_names = new Set(prev.map((e) => e.file.name))
      return [
        ...prev,
        ...incoming.filter((e) => !existing_names.has(e.file.name)),
      ]
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
    async (
      company_id: string,
      entries: QueuedFile[]
    ): Promise<DocumentResponse[] | null> => {
      const form = new FormData()
      for (const entry of entries) form.append("files", entry.file)
      const res = await fetch(
        `/api/ingestion/companies/${encodeURIComponent(company_id)}/documents`,
        { method: "POST", body: form }
      )
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) {
        set_error(format_error_payload(data))
        return null
      }
      return (Array.isArray(data) ? data : []) as DocumentResponse[]
    },
    []
  )

  /**
   * Direct-to-Supabase upload via signed URLs. Bypasses the backend entirely
   * for the file bytes, so free-tier hosts cannot become a transfer bottleneck.
   */
  const upload_via_signed_urls = useCallback(
    async (
      company_id: string,
      entries: QueuedFile[],
      tickets: UploadTicket[]
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
          set_error(
            `Upload of ${entry.file.name} failed (${put_response.status}): ${body.slice(0, 200)}`
          )
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
        }
      )
      const confirm_data: unknown = await confirm_res.json().catch(() => ({}))
      if (!confirm_res.ok) {
        set_error(format_error_payload(confirm_data))
        return null
      }
      return (
        Array.isArray(confirm_data) ? confirm_data : []
      ) as DocumentResponse[]
    },
    []
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
        }
      )
      const mint_data: unknown = await mint_res.json().catch(() => ({}))
      if (!mint_res.ok) {
        set_error(format_error_payload(mint_data))
        return
      }
      const mint_parsed = mint_data as Partial<UploadsMintResponse>

      let uploaded: DocumentResponse[] | null
      if (mint_parsed.mode === "direct" && Array.isArray(mint_parsed.uploads)) {
        uploaded = await upload_via_signed_urls(
          selected_company_id,
          queued_files,
          mint_parsed.uploads
        )
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

  useEffect(() => {
    if (
      !pending_upload_company_id ||
      pending_upload_company_id !== selected_company_id
    )
      return
    if (queued_files.length === 0) return
    void (async () => {
      await upload_queued()
      set_pending_upload_company_id(null)
    })()
  }, [
    pending_upload_company_id,
    queued_files.length,
    selected_company_id,
    upload_queued,
  ])

  // ── Embed ──────────────────────────────────────────────────────────────────

  const trigger_embed = useCallback(async () => {
    if (!selected_company_id) return
    set_triggering_embed(true)
    set_error(null)
    try {
      const res = await fetch(
        `/api/ingestion/companies/${encodeURIComponent(selected_company_id)}/embed`,
        { method: "POST" }
      )
      const data: unknown = await res.json().catch(() => ({}))
      if (!res.ok) {
        set_error(format_error_payload(data))
        return
      }
      await load_documents(selected_company_id)
    } finally {
      set_triggering_embed(false)
    }
  }, [selected_company_id, load_documents])

  const can_create_company =
    company_name.trim().length > 0 && company_email.trim().length > 0
  const selected_company = companies.find((c) => c.id === selected_company_id)
  const pending_document_count = documents.filter(
    (doc) => !doc.is_embedded && doc.status !== "failed"
  ).length

  return (
    <div className="flex min-h-svh w-full min-w-0 flex-col overflow-x-hidden bg-[#f6f8fb] text-[#061b3b]">
      <AppNavbar is_signed_in />
      <main className="w-full min-w-0 flex-1 p-4 sm:p-[18px]">
        {page_loading ? (
          <div className="flex flex-col items-center justify-center gap-3 py-24 text-muted-foreground">
            <Loader2 className="size-8 animate-spin text-primary" />
            <p className="text-sm">Loading agents...</p>
          </div>
        ) : (
          <div className="grid min-h-[calc(100svh-104px)] gap-6 lg:grid-cols-[425px_minmax(0,1fr)]">
            <aside className="rounded-2xl border border-[#dce4ef] bg-white p-6">
              <div className="flex items-center justify-between">
                <h1 className="font-serif text-lg text-[#123f88]">agents</h1>
                <button
                  type="button"
                  onClick={() => void bootstrap()}
                  className="rounded p-1 text-[#8aa0bd] hover:bg-[#f1f5fa]"
                  aria-label="Refresh agents"
                >
                  <RefreshCw className="size-4" />
                </button>
              </div>
              <div className="mt-4 flex flex-col gap-3">
                {companies.length === 0 ? (
                  <p className="py-8 text-center text-sm text-[#8aa0bd]">
                    No agents yet. Create one to upload documents.
                  </p>
                ) : (
                  companies.map((c) => (
                    <button
                      type="button"
                      key={c.id}
                      onClick={() => {
                        set_selected_company_id(c.id)
                        set_show_create_form(false)
                      }}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-2xl border px-[18px] py-4 text-left transition-colors",
                        c.id === selected_company_id
                          ? "border-[#d6e2f3] bg-[#edf4fd]"
                          : "border-[#dce4ef] bg-white hover:bg-[#f8fafc]"
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-serif text-[18px] leading-tight text-[#061b3b]">
                          {c.name}
                        </span>
                        <span className="mt-1 block text-sm text-[#8aa0bd]">
                          {c.id === selected_company_id
                            ? `${documents.length} documents`
                            : "View documents"}
                        </span>
                      </span>
                      <span
                        className="size-3 shrink-0 rounded-full bg-[#22c55e]"
                        aria-label="Agent active"
                      />
                    </button>
                  ))
                )}
              </div>
              <button
                type="button"
                onClick={() => set_show_create_form((value) => !value)}
                className="mt-5 flex h-[54px] w-full items-center justify-center gap-2 rounded-xl bg-[#2563eb] text-lg font-semibold text-white transition-colors hover:bg-[#1d4ed8]"
              >
                <Plus className="size-5" /> New agent
              </button>
              {show_create_form && (
                <div className="mt-3 space-y-2 rounded-xl border border-[#dce4ef] bg-[#f8fafc] p-3">
                  <input
                    value={company_name}
                    onChange={(e) => set_company_name(e.target.value)}
                    placeholder="Agent name *"
                    className="h-9 w-full rounded-lg border border-[#b9cdeb] bg-white px-3 text-sm"
                  />
                  <input
                    type="email"
                    value={company_email}
                    onChange={(e) => set_company_email(e.target.value)}
                    placeholder="Email *"
                    className="h-9 w-full rounded-lg border border-[#b9cdeb] bg-white px-3 text-sm"
                  />
                  <input
                    type="tel"
                    value={company_phone}
                    onChange={(e) => set_company_phone(e.target.value)}
                    placeholder="Phone (optional)"
                    className="h-9 w-full rounded-lg border border-[#b9cdeb] bg-white px-3 text-sm"
                  />
                  <textarea
                    value={company_description}
                    maxLength={300}
                    rows={2}
                    onChange={(e) => set_company_description(e.target.value)}
                    placeholder="Purpose (optional)"
                    className="w-full resize-none rounded-lg border border-[#b9cdeb] bg-white px-3 py-2 text-sm"
                  />
                  <Button
                    type="button"
                    className="w-full bg-[#2563eb] text-white hover:bg-[#1d4ed8]"
                    disabled={!can_create_company || creating_company}
                    onClick={() => void create_company()}
                  >
                    {creating_company ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      "Create agent"
                    )}
                  </Button>
                </div>
              )}
            </aside>

            <div className="min-w-0 space-y-6">
              <section className="rounded-2xl border border-[#dce4ef] bg-white p-6">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="font-serif text-xl text-[#061b3b]">
                    Upload documents
                  </h2>
                  <span className="truncate text-sm text-[#8aa0bd]">
                    {selected_company?.name ?? "Select an agent"}
                  </span>
                </div>
                <input
                  ref={file_input_ref}
                  type="file"
                  multiple
                  accept=".pdf,application/pdf"
                  className="sr-only"
                  onChange={(e) => {
                    if (e.target.files) enqueue_files(e.target.files)
                    if (file_input_ref.current)
                      file_input_ref.current.value = ""
                  }}
                  disabled={!selected_company_id}
                />
                <button
                  type="button"
                  disabled={!selected_company_id}
                  onClick={() => file_input_ref.current?.click()}
                  onDragEnter={(e) => {
                    e.preventDefault()
                    set_drag_active(true)
                  }}
                  onDragOver={(e) => {
                    e.preventDefault()
                    set_drag_active(true)
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault()
                    set_drag_active(false)
                  }}
                  onDrop={(e) => {
                    e.preventDefault()
                    set_drag_active(false)
                    if (!selected_company_id) return
                    if (e.dataTransfer.files?.length)
                      enqueue_files(e.dataTransfer.files)
                  }}
                  className={cn(
                    "mt-5 flex min-h-[222px] w-full flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-[#8dbdff] bg-[#fbfcfe] px-4 text-center transition-all",
                    drag_active
                      ? "scale-[1.01] border-[#2563eb] bg-[#f0f6ff]"
                      : "",
                    "hover:border-[#2563eb] hover:bg-[#f7fbff]",
                    "disabled:pointer-events-none disabled:opacity-40"
                  )}
                >
                  <div className="size-14 rounded-2xl bg-[#edf4ff]" />
                  <div>
                    <p className="font-serif text-lg text-[#061b3b]">
                      {drag_active
                        ? "Drop to add files"
                        : "Drop files or click to browse"}
                    </p>
                    <p className="mt-2 text-sm text-[#8aa0bd]">
                      PDF documents up to 25MB
                    </p>
                  </div>
                </button>
                {queued_files.length > 0 && (
                  <div className="mt-4 flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-medium text-muted-foreground">
                        {queued_files.length} file
                        {queued_files.length !== 1 ? "s" : ""} ready to upload
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
                        <QueuedFileRow
                          key={entry.id}
                          entry={entry}
                          on_remove={remove_queued_file}
                        />
                      ))}
                    </div>
                    <Button
                      type="button"
                      className="mt-1 w-full gap-2 bg-[#2563eb] text-white hover:bg-[#1d4ed8]"
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
                          Upload {queued_files.length} file
                          {queued_files.length !== 1 ? "s" : ""}
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </section>

              <section className="overflow-hidden rounded-2xl border border-[#dce4ef] bg-white">
                <div className="flex items-center justify-between gap-3 px-6 py-5">
                  <h2 className="font-serif text-xl text-[#061b3b]">
                    Uploaded documents
                  </h2>
                  <button
                    type="button"
                    disabled={!selected_company_id || triggering_embed}
                    onClick={() => selected_company_id && void trigger_embed()}
                    className="rounded-full bg-[#fdf0d9] px-3 py-1 text-sm text-[#a25800] disabled:opacity-50"
                  >
                    {triggering_embed
                      ? "Embedding…"
                      : `${pending_document_count} embed pending`}
                  </button>
                </div>
                {!selected_company_id ? (
                  <div className="flex flex-col items-center justify-center gap-3 border-t border-[#edf1f6] py-16 text-[#8aa0bd]">
                    <BrainCircuit className="size-8 opacity-30" />
                    <p className="text-sm">
                      Select an agent to see its documents.
                    </p>
                  </div>
                ) : list_loading && documents.length === 0 ? (
                  <div className="flex justify-center py-12">
                    <Loader2 className="size-6 animate-spin text-muted-foreground" />
                  </div>
                ) : documents.length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-3 border-t border-[#edf1f6] py-16 text-[#8aa0bd]">
                    <FolderOpen className="size-8 opacity-30" />
                    <p className="text-sm">
                      No documents yet. Upload some above.
                    </p>
                  </div>
                ) : (
                  <div className="border-t border-[#edf1f6]">
                    {documents.map((doc) => (
                      <DocumentCard
                        key={doc.id}
                        doc={doc}
                        is_new={new_doc_ids.has(doc.id)}
                      />
                    ))}
                  </div>
                )}
              </section>

              {error && (
                <div
                  role="alert"
                  className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                >
                  <span className="flex-1">{error}</span>
                  <button
                    type="button"
                    onClick={() => set_error(null)}
                    className="shrink-0 opacity-70 hover:opacity-100"
                  >
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
