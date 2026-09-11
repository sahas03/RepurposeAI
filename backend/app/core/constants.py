"""Shared enums and constant values used across the application."""
from enum import Enum


class RoleName(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    VIEWER = "viewer"


# Default permission sets per role. Permissions are simple "resource:action" strings
# checked by app.core.security.require_permission.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    RoleName.ADMIN: ["*"],
    RoleName.RESEARCHER: [
        "project:read", "project:write", "project:delete",
        "experiment:read", "experiment:write", "experiment:delete",
        "dataset:read", "dataset:write", "dataset:delete",
        "analysis:read", "analysis:write",
        "repurposing:run",
        "prediction:read",
        "recommendation:read", "recommendation:write",
        "notification:read",
        "search:read",
        "drug:read", "disease:read", "gene:read", "target:read", "compound:read", "interaction:read",
    ],
    RoleName.ANALYST: [
        "project:read", "project:write",
        "experiment:read", "experiment:write",
        "dataset:read", "dataset:write",
        "analysis:read", "analysis:write",
        "repurposing:run",
        "prediction:read",
        "recommendation:read", "recommendation:write",
        "notification:read",
        "search:read",
        "drug:read", "disease:read", "gene:read", "target:read", "compound:read", "interaction:read",
    ],
    RoleName.VIEWER: [
        "project:read",
        "experiment:read",
        "dataset:read",
        "analysis:read",
        "prediction:read",
        "recommendation:read", "recommendation:write",
        "notification:read",
        "search:read",
        "drug:read", "disease:read", "gene:read", "target:read", "compound:read", "interaction:read",
    ],
}


class ProjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    COMPLETED = "COMPLETED"
    ON_HOLD = "ON_HOLD"


class ExperimentStatus(str, Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ACTIVE_EXPERIMENT_STATUSES = {
    ExperimentStatus.QUEUED,
    ExperimentStatus.RUNNING,
    ExperimentStatus.ANALYZING,
}


class ExperimentType(str, Enum):
    DRUG_REPURPOSING = "drug_repurposing"
    GENE_EXPRESSION = "gene_expression"
    TARGET_ANALYSIS = "target_analysis"
    DISEASE_ANALYSIS = "disease_analysis"
    COMPOUND_SIMILARITY = "compound_similarity"
    CUSTOM = "custom"


class DatasetStatus(str, Enum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    INVALID = "INVALID"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class DatasetFileType(str, Enum):
    CSV = "csv"
    JSON = "json"
    XLSX = "xlsx"
    TSV = "tsv"
    FASTA = "fasta"
    FASTQ = "fastq"


class AnalysisType(str, Enum):
    GENE_EXPRESSION = "gene_expression"
    DIFFERENTIAL_EXPRESSION = "differential_expression"
    COMPOUND_SIMILARITY = "compound_similarity"
    TARGET_ANALYSIS = "target_analysis"
    DISEASE_ANALYSIS = "disease_analysis"
    DRUG_REPURPOSING = "drug_repurposing"
    DATASET_QUALITY = "dataset_quality"
    STATISTICAL_ANALYSIS = "statistical_analysis"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PROGRESS = "PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_JOB_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}


class JobType(str, Enum):
    DATASET_VALIDATION = "dataset_validation"
    DATASET_PROCESSING = "dataset_processing"
    ANALYSIS = "analysis"
    DRUG_REPURPOSING = "drug_repurposing"
    PREDICTION = "prediction"
    ANALYTICS_AGGREGATION = "analytics_aggregation"
    CLEANUP = "cleanup"


class NotificationType(str, Enum):
    EXPERIMENT_STARTED = "experiment_started"
    EXPERIMENT_COMPLETED = "experiment_completed"
    EXPERIMENT_FAILED = "experiment_failed"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    PREDICTION_GENERATED = "prediction_generated"
    DATASET_VALIDATION_FAILED = "dataset_validation_failed"
    HIGH_CONFIDENCE_CANDIDATE = "high_confidence_candidate"
    SYSTEM = "system"


class RecommendationType(str, Enum):
    DRUG_CANDIDATE = "drug_candidate"
    HIGH_CONFIDENCE_PREDICTION = "high_confidence_prediction"
    DATASET_ATTENTION = "dataset_attention"
    FAILED_EXPERIMENT = "failed_experiment"
    UNUSUAL_RESULT = "unusual_result"
    SUGGESTED_ANALYSIS = "suggested_analysis"


class RecommendationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISMISSED = "DISMISSED"
    ACTED_ON = "ACTED_ON"


class RecommendationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InteractionType(str, Enum):
    DRUG_TARGET = "drug_target"
    DRUG_GENE = "drug_gene"
    GENE_DISEASE = "gene_disease"
    DRUG_DISEASE = "drug_disease"
    COMPOUND_TARGET = "compound_target"
    PROTEIN_PROTEIN = "protein_protein"


class EvidenceLevel(str, Enum):
    COMPUTATIONAL_PREDICTION = "computational_prediction"
    SUPPORTING_EVIDENCE = "supporting_evidence"
    EXPERIMENTAL_EVIDENCE = "experimental_evidence"
    CLINICAL_EVIDENCE = "clinical_evidence"


class AuditAction(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"
    EXPERIMENT_CREATE = "experiment_create"
    EXPERIMENT_START = "experiment_start"
    EXPERIMENT_CANCEL = "experiment_cancel"
    DATASET_UPLOAD = "dataset_upload"
    DATASET_DELETE = "dataset_delete"
    ANALYSIS_START = "analysis_start"
    ANALYSIS_COMPLETE = "analysis_complete"
    PREDICTION_GENERATE = "prediction_generate"
    DATA_DELETE = "data_delete"
    PERMISSION_CHANGE = "permission_change"
    USER_UPDATE = "user_update"


DEMO_DATA_DISCLAIMER = (
    "DEMO/SYNTHETIC DATA - generated for demonstration purposes only. "
    "Not derived from real experimental or clinical sources."
)
