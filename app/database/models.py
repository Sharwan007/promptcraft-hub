"""SQLAlchemy models (normalized). JSON columns hold small list/dict fields only."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.security import utcnow


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(40), default="folder")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    subcategories: Mapped[list["Subcategory"]] = relationship(back_populates="category", order_by="Subcategory.name")


class Subcategory(TimestampMixin, Base):
    __tablename__ = "subcategories"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_subcategory_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[Category] = relationship(back_populates="subcategories")


class Tag(TimestampMixin, Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class PromptTag(Base):
    __tablename__ = "prompt_tags"
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True)


class Prompt(TimestampMixin, Base):
    __tablename__ = "prompts"
    __table_args__ = (
        Index("ix_prompts_listing", "published", "archived", "category_id"),
        Index("ix_prompts_title", "title"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    full_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True, nullable=False)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id"), index=True, nullable=True)
    user_role: Mapped[str] = mapped_column(String(120), default="", index=True)
    use_case: Mapped[str] = mapped_column(String(200), default="")
    ai_tools: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(20), default="Beginner", index=True)
    expected_output: Mapped[str] = mapped_column(Text, default="")
    required_inputs: Mapped[list] = mapped_column(JSON, default=list)
    example_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    example_output: Mapped[str] = mapped_column(Text, default="")
    why_it_works: Mapped[str] = mapped_column(Text, default="")
    customization_tips: Mapped[list] = mapped_column(JSON, default=list)
    common_mistakes: Mapped[list] = mapped_column(JSON, default=list)
    constraints: Mapped[list] = mapped_column(JSON, default=list)
    components: Mapped[dict] = mapped_column(JSON, default=dict)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    copy_count: Mapped[int] = mapped_column(Integer, default=0)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    category: Mapped[Category] = relationship(lazy="joined")
    subcategory: Mapped[Subcategory | None] = relationship(lazy="joined")
    tags: Mapped[list[Tag]] = relationship(secondary="prompt_tags", lazy="selectin", order_by="Tag.name")


class LocalProfile(TimestampMixin, Base):
    __tablename__ = "local_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), default="Local User")
    role: Mapped[str] = mapped_column(String(80), default="")
    theme: Mapped[str] = mapped_column(String(10), default="system")
    default_ai_tool: Mapped[str] = mapped_column(String(40), default="Tool-independent")
    view_mode: Mapped[str] = mapped_column(String(10), default="grid")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("profile_id", "prompt_id", name="uq_favorite"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("local_profile.id", ondelete="CASCADE"), index=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CustomPrompt(TimestampMixin, Base):
    __tablename__ = "custom_prompts"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("local_profile.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source_prompt_id: Mapped[int | None] = mapped_column(ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True)
    origin: Mapped[str] = mapped_column(String(30), default="manual")
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    category: Mapped[Category | None] = relationship(lazy="joined")
    versions: Mapped[list["CustomPromptVersion"]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan", order_by="CustomPromptVersion.version.desc()"
    )


class CustomPromptVersion(Base):
    __tablename__ = "custom_prompt_versions"
    __table_args__ = (UniqueConstraint("custom_prompt_id", "version", name="uq_custom_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    custom_prompt_id: Mapped[int] = mapped_column(ForeignKey("custom_prompts.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    change_note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prompt: Mapped[CustomPrompt] = relationship(back_populates="versions")


class LearningModule(TimestampMixin, Base):
    __tablename__ = "learning_modules"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    good_example: Mapped[str] = mapped_column(Text, default="")
    weak_example: Mapped[str] = mapped_column(Text, default="")
    tips: Mapped[list] = mapped_column(JSON, default=list)
    common_mistakes: Mapped[list] = mapped_column(JSON, default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[list["KnowledgeCheck"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="KnowledgeCheck.id", lazy="selectin"
    )


class KnowledgeCheck(Base):
    __tablename__ = "knowledge_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("learning_modules.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list)
    correct_index: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    module: Mapped[LearningModule] = relationship(back_populates="checks")


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("profile_id", "module_id", name="uq_progress"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("local_profile.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("learning_modules.id", ondelete="CASCADE"), index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class BeforeAfterExample(TimestampMixin, Base):
    __tablename__ = "before_after_examples"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    scenario: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    weak_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    problems: Mapped[list] = mapped_column(JSON, default=list)
    improved_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    improvements: Mapped[list] = mapped_column(JSON, default=list)
    why_better: Mapped[str] = mapped_column(Text, default="")
    expected_difference: Mapped[str] = mapped_column(Text, default="")
    weak_score: Mapped[int] = mapped_column(Integer, default=0)
    improved_score: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class GlossaryTerm(TimestampMixin, Base):
    __tablename__ = "glossary_terms"
    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    example: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)


class PromptUsageEvent(Base):
    """Local-only usage counters. Never stores prompt text."""
    __tablename__ = "prompt_usage_events"
    __table_args__ = (Index("ix_usage_type", "event_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_id: Mapped[int | None] = mapped_column(ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AdminCredential(TimestampMixin, Base):
    __tablename__ = "admin_credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    pin_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    salt: Mapped[str] = mapped_column(String(64), nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_nonce: Mapped[str] = mapped_column(String(64), nullable=False)


class ImportHistory(Base):
    __tablename__ = "import_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="preview")
    mode: Mapped[str] = mapped_column(String(30), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class RecentlyViewedPrompt(Base):
    __tablename__ = "recently_viewed_prompts"
    __table_args__ = (UniqueConstraint("profile_id", "prompt_id", name="uq_recent"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("local_profile.id", ondelete="CASCADE"), index=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ValidationErrorLog(Base):
    """Recent server-side validation failures (field names and messages only, never values)."""
    __tablename__ = "validation_error_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(160), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
