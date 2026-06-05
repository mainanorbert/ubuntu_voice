"""Application settings loaded from environment variables."""

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API process."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenAI-compatible base URL for OpenRouter",
    )
    openrouter_model: str = Field(
        default="openai/gpt-4.1-mini",
        description="OpenRouter model slug for chat completions",
    )
    evaluation_model: str = Field(
        default="openai/gpt-5.4",
        description="OpenRouter model slug used by independent RAG evaluators",
    )
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        description="OpenRouter / OpenAI-compatible embedding model slug",
    )
    embedding_dimensions: int = Field(
        default=1536,
        ge=32,
        le=8192,
        description="Vector size for document_chunks.embedding; must match the embedding model output",
    )
    embedding_max_chars_per_chunk: int = Field(
        default=2000,
        ge=256,
        le=32000,
        description="Maximum characters per text chunk before embedding",
    )
    embedding_chunk_overlap_chars: int = Field(
        default=200,
        ge=0,
        le=4096,
        description="Character overlap between consecutive chunks",
    )
    embedding_api_batch_size: int = Field(
        default=64,
        ge=1,
        le=256,
        description="Maximum number of texts sent per embeddings API request",
    )
    rag_top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of nearest chunks to retrieve per query",
    )
    guardrail_max_input_tokens: int = Field(
        default=500,
        ge=16,
        le=8000,
        description=(
            "Maximum number of tokens permitted in a single user prompt. Requests above this "
            "limit are rejected before any embedding or LLM call so cost stays predictable and "
            "answers stay focused. Tune via GUARDRAIL_MAX_INPUT_TOKENS in .env."
        ),
    )
    guardrail_token_encoding: str = Field(
        default="cl100k_base",
        description=(
            "tiktoken encoding name used for input token counting. cl100k_base is correct for "
            "GPT-4 / GPT-3.5 / text-embedding-3-* models and is a safe default for OpenRouter."
        ),
    )
    guardrail_phone_country_code: str = Field(
        default="254",
        description=(
            "Country dialing code (without '+') used to detect monitored phone numbers in "
            "model replies. Defaults to Kenya (+254)."
        ),
    )
    resend_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESEND_API_KEY"),
        description="Optional Resend API key used for emerging-conflict alert emails.",
    )
    twilio_account_sid: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_ACCOUNT_SID"),
        description="Optional Twilio Account SID used to send WhatsApp replies.",
    )
    twilio_auth_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_AUTH_TOKEN"),
        description="Optional Twilio Auth Token used to send WhatsApp replies.",
    )
    twilio_whatsapp_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_WHATSAPP_NUMBER"),
        description="Optional Twilio WhatsApp sender, formatted like whatsapp:+15551234567.",
    )
    twilio_sms_from_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_SMS_FROM_NUMBER"),
        description="Optional Twilio SMS sender number in E.164 format.",
    )
    twilio_sms_to_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TWILIO_SMS_TO_NUMBER"),
        description="Optional Twilio SMS recipient number in E.164 format for conflict alerts.",
    )
    pushover_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUSHOVER_USER"),
        description="Optional Pushover recipient user key for conflict-alert push notifications.",
    )
    pushover_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("PUSHOVER_TOKEN"),
        description="Optional Pushover application token for conflict-alert push notifications.",
    )
    rag_similarity_threshold: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description=(
            "Cosine similarity floor (0–1). Queries whose best chunk similarity falls below "
            "this value are considered out-of-scope and receive a company-aware refusal. "
            "For OpenAI text-embedding-3-* models, relevant matches typically score 0.25–0.60 "
            "and unrelated noise sits below 0.15. Tune via RAG_SIMILARITY_THRESHOLD in .env."
        ),
    )
    clerk_secret_key: str = Field(..., description="Clerk secret key for verifying session JWTs")
    clerk_authorized_parties: str = Field(
        default="https://css-f-brown.vercel.app,http://localhost:3000",
        description="Comma-separated frontend origins allowed in Clerk session tokens (azp)",
    )
    database_url: str = Field(
        validation_alias=AliasChoices("EIVEN_SERVICE_URL", "DATABASE_URL"),
        description="Aiven PostgreSQL Service URI (postgres:// or postgresql+psycopg2://)",
    )
    upload_root: str = Field(
        default="./storage",
        description="Root directory where uploaded files are stored locally when Supabase is not configured",
    )
    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL"),
        description="Supabase project URL used for server-side Storage access",
    )
    supabase_service_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SERVICE_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_KEY"),
        description="Server-only Supabase API key used to bypass Storage RLS from the backend",
    )
    supabase_bucket: str = Field(
        default="documents",
        validation_alias=AliasChoices("SUPABASE_BUCKET", "SUPABASE_STORAGE_BUCKET"),
        description="Supabase Storage bucket name for uploaded document binaries",
    )
    cors_allowed_origins: str = Field(
        default="https://css-f-brown.vercel.app",
        description=(
            "Comma-separated browser origins allowed to call this API (CORS). "
            "Set explicitly in production to your deployed frontend origin(s)."
        ),
    )
    cors_allow_credentials: bool = Field(
        default=False,
        description=(
            "Whether browsers may send credentialed cross-origin requests (cookies). "
            "Enable only if your frontend uses credentials mode for API calls."
        ),
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize postgres:// shorthand to the SQLAlchemy psycopg2 dialect prefix."""
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg2://", 1)
        return v

    @field_validator("supabase_url", mode="before")
    @classmethod
    def normalize_supabase_url(cls, v: str | None) -> str | None:
        """Remove trailing slashes from the configured Supabase project URL."""
        if isinstance(v, str):
            stripped = v.strip()
            return stripped.rstrip("/") or None
        return v
