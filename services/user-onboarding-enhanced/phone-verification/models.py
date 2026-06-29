import enum
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey,
    Enum, Text, JSON, BigInteger, Float, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

# --- Base Class and Mixins ---

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and common utility methods.
    """
    pass

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        doc="Timestamp of when the record was created."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Timestamp of when the record was last updated."
    )

class SoftDeleteMixin:
    """Mixin for soft deletion support."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of when the record was soft-deleted."
    )

class AuditMixin:
    """Mixin for created_by and updated_by audit fields."""
    created_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Identifier of the user or system that created the record."
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Identifier of the user or system that last updated the record."
    )

# --- Enums ---

class DatabaseStatus(enum.Enum):
    """Status of the tracked database connection."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

class ColumnDataType(enum.Enum):
    """Common PostgreSQL data types."""
    TEXT = "text"
    VARCHAR = "varchar"
    INTEGER = "integer"
    BIGINT = "bigint"
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    JSONB = "jsonb"
    UUID = "uuid"
    ARRAY = "array"
    OTHER = "other"

class IndexType(enum.Enum):
    """Types of indexes."""
    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"
    GIST = "gist"
    BRIN = "brin"

# --- Models ---

class Database(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a single PostgreSQL database instance being tracked.
    """
    __tablename__ = "databases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Primary key.")
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Name of the database.")
    host: Mapped[str] = mapped_column(String(255), nullable=False, doc="Hostname or IP address.")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=5432, doc="Port number.")
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, doc="PostgreSQL version string.")
    status: Mapped[DatabaseStatus] = mapped_column(
        Enum(DatabaseStatus, name="database_status"),
        nullable=False,
        default=DatabaseStatus.ACTIVE,
        doc="Current connection status of the database."
    )
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the last successful metadata scan."
    )
    connection_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        doc="Additional connection details (e.g., user, maintenance DB)."
    )

    # Relationships
    schemas: Mapped[list["Schema"]] = relationship(
        "Schema",
        back_populates="database",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("host", "port", name="uq_database_host_port"),
        Index("ix_database_name", "name"),
    )

class Schema(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a schema within a tracked database (e.g., 'public', 'app').
    """
    __tablename__ = "schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Primary key.")
    database_id: Mapped[int] = mapped_column(
        ForeignKey("databases.id", ondelete="CASCADE"),
        nullable=False,
        doc="Foreign key to the parent database."
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Name of the schema.")
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, doc="Owner of the schema.")

    # Relationships
    database: Mapped["Database"] = relationship("Database", back_populates="schemas")
    tables: Mapped[list["Table"]] = relationship(
        "Table",
        back_populates="schema",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("database_id", "name", name="uq_schema_database_name"),
        Index("ix_schema_name", "name"),
    )

class Table(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a table within a tracked schema.
    """
    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Primary key.")
    schema_id: Mapped[int] = mapped_column(
        ForeignKey("schemas.id", ondelete="CASCADE"),
        nullable=False,
        doc="Foreign key to the parent schema."
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Name of the table.")
    row_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, doc="Estimated number of rows.")
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, doc="Total size of the table and its indexes in bytes.")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Comment/description of the table.")
    is_partitioned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="Whether the table is a partitioned table.")

    # Relationships
    schema: Mapped["Schema"] = relationship("Schema", back_populates="tables")
    columns: Mapped[list["ColumnMetadata"]] = relationship(
        "ColumnMetadata",
        back_populates="table",
        cascade="all, delete-orphan"
    )
    indexes: Mapped[list["IndexMetadata"]] = relationship(
        "IndexMetadata",
        back_populates="table",
        cascade="all, delete-orphan"
    )
    foreign_keys: Mapped[list["ForeignKeyMetadata"]] = relationship(
        "ForeignKeyMetadata",
        back_populates="source_table",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("schema_id", "name", name="uq_table_schema_name"),
        Index("ix_table_name", "name"),
    )

class ColumnMetadata(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a column within a tracked table.
    """
    __tablename__ = "column_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Primary key.")
    table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False,
        doc="Foreign key to the parent table."
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Name of the column.")
    data_type: Mapped[ColumnDataType] = mapped_column(
        Enum(ColumnDataType, name="column_data_type"),
        nullable=False,
        doc="The base data type of the column."
    )
    is_nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, doc="Whether the column can contain NULL values.")
    default_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="The default value expression for the column.")
    character_maximum_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, doc="Maximum length for character types.")
    numeric_precision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, doc="Numeric precision for numeric types.")
    position: Mapped[int] = mapped_column(Integer, nullable=False, doc="Ordinal position of the column in the table.")
    statistics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        doc="Statistical data (e.g., distinct values, histogram) from ANALYZE."
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Comment/description of the column.")

    # Relationships
    table: Mapped["Table"] = relationship("Table", back_populates="columns")

    __table_args__ = (
        UniqueConstraint("table_id", "name", name="uq_column_table_name"),
        Index("ix_column_table_id_position", "table_id", "position"),
    )

class IndexMetadata(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents an index associated with a tracked table.
    """
    __tablename__ = "index_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Primary key.")
    table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False,
        doc="Foreign key to the parent table."
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Name of the index.")
    index_type: Mapped[IndexType] = mapped_column(
        Enum(IndexType, name="index_type"),
        nullable=False,
        doc="The type of index (e.g., btree, hash, gin)."
    )
    is_unique: Mapped[bool] = mapped_column(Boolean, nullable=False, doc="Whether the index enforces uniqueness.")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="Whether the index is the primary key index.")
    definition: Mapped[str] = mapped_column(Text, nullable=False, doc="The full DDL definition of the index.")
    columns_list: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        doc="JSON array of column names included in the index."
    )
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, doc="Size of the index on disk.")

    # Relationships
    table: Mapped["Table"] = relationship("Table", back_populates="indexes")

    __table_args__ = (
        UniqueConstraint("table_id", "name", name="uq_index_table_name"),
        Index("ix_index_name", "name"),
    )

class ForeignKeyMetadata(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Represents a foreign key constraint between two tables.
    """
    __tablename__ = "foreign_key_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Primary key.")
    source_table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False,
        doc="Foreign key to the source table (the one with the FK column)."
    )
    target_table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="RESTRICT"), # Use RESTRICT to prevent accidental deletion of target table
        nullable=False,
        doc="Foreign key to the target table (the one being referenced)."
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Name of the foreign key constraint.")
    source_columns: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        doc="JSON array of source column names."
    )
    target_columns: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        doc="JSON array of target column names."
    )
    on_update: Mapped[str] = mapped_column(String(50), nullable=False, default="NO ACTION", doc="Action on UPDATE (e.g., CASCADE, RESTRICT).")
    on_delete: Mapped[str] = mapped_column(String(50), nullable=False, default="NO ACTION", doc="Action on DELETE (e.g., CASCADE, RESTRICT).")

    # Relationships
    source_table: Mapped["Table"] = relationship(
        "Table",
        foreign_keys=[source_table_id],
        back_populates="foreign_keys"
    )
    target_table: Mapped["Table"] = relationship(
        "Table",
        foreign_keys=[target_table_id],
        # No back_populates here to avoid circular reference complexity, 
        # as the relationship is one-way (source -> target) for metadata tracking.
    )

    __table_args__ = (
        UniqueConstraint("source_table_id", "name", name="uq_fk_source_table_name"),
        Index("ix_fk_target_table_id", "target_table_id"),
    )

# --- Utility to get all models for table count ---
def get_all_models() -> List:
    """Returns a list of all defined SQLAlchemy models."""
    return [
        Database,
        Schema,
        Table,
        ColumnMetadata,
        IndexMetadata,
        ForeignKeyMetadata,
    ]

# The total number of tables is 6.
