import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AnalysisType, AuditAction, JobStatus, JobType
from app.core.exceptions import NotFoundError
from app.models.analysis import Analysis
from app.models.user import User
from app.services.audit_service import log_action
from app.services.experiment_service import get_experiment_or_404, check_experiment_access
from app.services.job_service import create_job


def get_analysis_or_404(db: Session, analysis_id: uuid.UUID) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if not analysis:
        raise NotFoundError("Analysis was not found", code="ANALYSIS_NOT_FOUND")
    return analysis


def run_analysis(db: Session, user: User, experiment_id: uuid.UUID, dataset_id: uuid.UUID | None, analysis_type: AnalysisType, parameters: dict) -> tuple[Analysis, uuid.UUID]:
    experiment = get_experiment_or_404(db, experiment_id)
    check_experiment_access(db, user, experiment)

    analysis = Analysis(
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        analysis_type=analysis_type.value,
        status=JobStatus.QUEUED.value,
        parameters=parameters,
    )
    db.add(analysis)
    db.flush()
    db.refresh(analysis)

    job = create_job(
        db, JobType.ANALYSIS, user_id=user.id, project_id=experiment.project_id,
        experiment_id=experiment_id, analysis_id=analysis.id, dataset_id=dataset_id,
    )
    log_action(db, user.id, AuditAction.ANALYSIS_START, "analysis", str(analysis.id))
    db.commit()

    from app.workers.analysis_tasks import run_analysis_task
    run_analysis_task.delay(str(analysis.id), str(job.id))

    db.refresh(analysis)
    return analysis, job.id
