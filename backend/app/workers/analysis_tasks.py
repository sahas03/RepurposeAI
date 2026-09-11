"""Celery tasks that run experiments and generic analyses in the background."""
import uuid
from datetime import datetime, timezone

from app.ai.preprocessing.preprocessing import clean_numeric_frame, compute_dataframe_metadata, differential_expression
from app.biotech.disease_analysis import get_disease_associated_genes
from app.biotech.drug_repurposing import run_repurposing_analysis
from app.biotech.gene_analysis import gene_expression_summary
from app.core.constants import AnalysisType, ExperimentStatus, ExperimentType, JobStatus, NotificationType
from app.data.loaders.dataset_loader import load_dataframe
from app.models.analysis import Analysis
from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.prediction import Prediction
from app.models.project import Project
from app.services.notification_service import create_notification
from app.utils.file_utils import get_storage
from app.websocket.handlers import publish_ws_event
from app.workers.celery_app import celery_app
from app.workers.task_utils import task_db


def _publish_experiment(experiment_id: str, event: str, status: str, progress: int, message: str) -> None:
    publish_ws_event(f"experiments:{experiment_id}", {
        "event": event, "status": status, "progress": progress, "message": message,
    })


@celery_app.task(name="app.workers.analysis_tasks.run_experiment_task", bind=True, max_retries=0)
def run_experiment_task(self, experiment_id: str, user_id: str) -> dict:
    exp_uuid = uuid.UUID(experiment_id)

    with task_db() as db:
        experiment = db.get(Experiment, exp_uuid)
        if not experiment or experiment.status == ExperimentStatus.CANCELLED.value:
            return {"status": "skipped"}
        experiment.status = ExperimentStatus.RUNNING.value
        experiment.started_at = datetime.now(timezone.utc)
        experiment.progress = 5
        project = db.get(Project, experiment.project_id)
        owner_id = project.owner_id

    _publish_experiment(experiment_id, "started", ExperimentStatus.RUNNING.value, 5, "Experiment started")

    try:
        if experiment.experiment_type == ExperimentType.DRUG_REPURPOSING.value:
            _run_drug_repurposing_experiment(experiment_id, owner_id)
        else:
            _run_generic_experiment(experiment_id)

        with task_db() as db:
            experiment = db.get(Experiment, exp_uuid)
            experiment.status = ExperimentStatus.COMPLETED.value
            experiment.progress = 100
            experiment.completed_at = datetime.now(timezone.utc)

        _publish_experiment(experiment_id, "completed", ExperimentStatus.COMPLETED.value, 100, "Experiment completed successfully")
        with task_db() as db:
            create_notification(
                db, owner_id, "Experiment completed",
                f"Experiment completed successfully.", NotificationType.EXPERIMENT_COMPLETED,
                {"experiment_id": experiment_id},
            )
        return {"status": "completed"}

    except Exception as exc:
        with task_db() as db:
            experiment = db.get(Experiment, exp_uuid)
            experiment.status = ExperimentStatus.FAILED.value
            experiment.completed_at = datetime.now(timezone.utc)
            create_notification(
                db, owner_id, "Experiment failed",
                f"Experiment failed: {exc}", NotificationType.EXPERIMENT_FAILED,
                {"experiment_id": experiment_id},
            )
        _publish_experiment(experiment_id, "failed", ExperimentStatus.FAILED.value, experiment.progress, str(exc))
        return {"status": "failed", "error": str(exc)}


def _run_drug_repurposing_experiment(experiment_id: str, owner_id) -> None:
    exp_uuid = uuid.UUID(experiment_id)
    with task_db() as db:
        experiment = db.get(Experiment, exp_uuid)
        disease_id = experiment.parameters.get("disease_id")
        if not disease_id:
            raise ValueError("drug_repurposing experiments require a 'disease_id' parameter")
        top_k = int(experiment.parameters.get("top_k", 20))
        experiment.status = ExperimentStatus.ANALYZING.value
        experiment.progress = 30
        project_id = experiment.project_id

    _publish_experiment(experiment_id, "progress", ExperimentStatus.ANALYZING.value, 30, "Gathering biotech evidence")

    result = None
    with task_db() as db:
        result = run_repurposing_analysis(db, uuid.UUID(disease_id), top_k=top_k)

    _publish_experiment(experiment_id, "progress", ExperimentStatus.ANALYZING.value, 70, "Scoring and ranking candidates")

    with task_db() as db:
        analysis = Analysis(
            experiment_id=exp_uuid,
            analysis_type=AnalysisType.DRUG_REPURPOSING.value,
            status=JobStatus.COMPLETED.value,
            progress=100,
            parameters={"disease_id": disease_id, "top_k": top_k},
            results={"candidate_pool_size": result["candidate_pool_size"], "prediction_count": len(result["results"])},
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(analysis)

        high_confidence_found = False
        for item in result["results"]:
            prediction = Prediction(
                project_id=project_id,
                experiment_id=exp_uuid,
                drug_id=uuid.UUID(item["drug_id"]),
                disease_id=uuid.UUID(disease_id),
                score=item["score"],
                confidence=item["confidence"],
                rank=item["rank"],
                explanation=item["explanation"],
                features=item["features"],
                model_version=item["model_version"],
            )
            db.add(prediction)
            if item["confidence"] >= 0.75:
                high_confidence_found = True

        if high_confidence_found:
            create_notification(
                db, owner_id, "High-confidence repurposing candidate found",
                f"A high-confidence drug repurposing candidate was found for '{result['disease_name']}'.",
                NotificationType.HIGH_CONFIDENCE_CANDIDATE,
                {"experiment_id": experiment_id, "disease_id": disease_id},
            )


def _run_generic_experiment(experiment_id: str) -> None:
    """Runs a basic dataset-quality/statistical pass for non-repurposing experiment types."""
    exp_uuid = uuid.UUID(experiment_id)
    with task_db() as db:
        experiment = db.get(Experiment, exp_uuid)
        experiment.status = ExperimentStatus.ANALYZING.value
        experiment.progress = 40
        dataset_id = experiment.parameters.get("dataset_id")

    _publish_experiment(experiment_id, "progress", ExperimentStatus.ANALYZING.value, 40, "Running analysis")

    results: dict = {"note": "No dataset supplied; experiment completed with no analysis output."}
    if dataset_id:
        with task_db() as db:
            dataset = db.get(Dataset, uuid.UUID(dataset_id))
            if dataset:
                storage = get_storage()
                content = storage.read(dataset.storage_path)
                df = load_dataframe(content, dataset.file_type)
                results = compute_dataframe_metadata(df)

    with task_db() as db:
        db.add(Analysis(
            experiment_id=exp_uuid,
            dataset_id=uuid.UUID(dataset_id) if dataset_id else None,
            analysis_type=AnalysisType.DATASET_QUALITY.value,
            status=JobStatus.COMPLETED.value,
            progress=100,
            parameters={"dataset_id": dataset_id},
            results=results,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))

    _publish_experiment(experiment_id, "progress", ExperimentStatus.ANALYZING.value, 90, "Finalizing results")


@celery_app.task(name="app.workers.analysis_tasks.run_analysis_task", bind=True, max_retries=0)
def run_analysis_task(self, analysis_id: str, job_id: str) -> dict:
    from app.services.job_service import update_job

    analysis_uuid = uuid.UUID(analysis_id)
    job_uuid = uuid.UUID(job_id)

    with task_db() as db:
        update_job(db, job_uuid, status=JobStatus.RUNNING, progress=10, message="Loading analysis inputs")
        analysis = db.get(Analysis, analysis_uuid)
        analysis.status = JobStatus.RUNNING.value
        analysis.started_at = datetime.now(timezone.utc)
        analysis_type = analysis.analysis_type
        dataset_id = analysis.dataset_id
        parameters = analysis.parameters or {}

    try:
        results = _execute_analysis(analysis_type, dataset_id, parameters)

        with task_db() as db:
            analysis = db.get(Analysis, analysis_uuid)
            analysis.status = JobStatus.COMPLETED.value
            analysis.progress = 100
            analysis.results = results
            analysis.completed_at = datetime.now(timezone.utc)
            update_job(db, job_uuid, status=JobStatus.COMPLETED, progress=100, message="Analysis completed", result=results)
        return {"status": "completed"}

    except Exception as exc:
        with task_db() as db:
            analysis = db.get(Analysis, analysis_uuid)
            analysis.status = JobStatus.FAILED.value
            analysis.error_message = str(exc)
            analysis.completed_at = datetime.now(timezone.utc)
            update_job(db, job_uuid, status=JobStatus.FAILED, error=str(exc))
        return {"status": "failed", "error": str(exc)}


def _execute_analysis(analysis_type: str, dataset_id, parameters: dict) -> dict:
    if dataset_id is None:
        raise ValueError(f"analysis_type '{analysis_type}' requires a dataset_id")

    with task_db() as db:
        dataset = db.get(Dataset, dataset_id)
        if not dataset:
            raise ValueError("Referenced dataset no longer exists")
        storage = get_storage()
        content = storage.read(dataset.storage_path)

    df = load_dataframe(content, dataset.file_type)

    if analysis_type == AnalysisType.DATASET_QUALITY.value:
        return compute_dataframe_metadata(df)

    if analysis_type == AnalysisType.STATISTICAL_ANALYSIS.value:
        numeric = clean_numeric_frame(df)
        return {"basic_statistics": compute_dataframe_metadata(df)["basic_statistics"], "row_count": len(df)}

    if analysis_type in (AnalysisType.GENE_EXPRESSION.value,):
        numeric = clean_numeric_frame(df)
        summaries = {col: gene_expression_summary(numeric[col].tolist()) for col in numeric.columns}
        return {"gene_expression_summary": summaries}

    if analysis_type == AnalysisType.DIFFERENTIAL_EXPRESSION.value:
        group_a = parameters.get("group_a_columns", [])
        group_b = parameters.get("group_b_columns", [])
        if not group_a or not group_b:
            raise ValueError("differential_expression requires 'group_a_columns' and 'group_b_columns' parameters")
        result_df = differential_expression(df, group_a, group_b)
        return {"rows": result_df.reset_index().to_dict(orient="records")[:500], "significant_count": int(result_df["significant"].sum())}

    if analysis_type == AnalysisType.COMPOUND_SIMILARITY.value:
        return compute_dataframe_metadata(df)

    if analysis_type in (AnalysisType.TARGET_ANALYSIS.value, AnalysisType.DISEASE_ANALYSIS.value):
        return compute_dataframe_metadata(df)

    raise ValueError(f"Unsupported analysis_type '{analysis_type}'")
