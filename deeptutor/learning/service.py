from __future__ import annotations

import time
import uuid

from deeptutor.learning.models import (
    ErrorRecord,
    LearningModule,
    LearningProgress,
    LearningStage,
    QuizAttempt,
    RetryAttempt,
)
from deeptutor.learning.storage import LearningStore


class LearningService:
    def __init__(self, store: LearningStore | None = None) -> None:
        self._store = store or LearningStore()

    def get_or_create(self, book_id: str) -> LearningProgress:
        existing = self._store.load(book_id)
        if existing is not None:
            return existing
        progress = LearningProgress(book_id=book_id)
        self._store.save(progress)  # persist immediately to prevent race
        return progress

    def init_modules(
        self, progress: LearningProgress, modules: list[LearningModule]
    ) -> None:
        progress.modules = modules
        for mod in modules:
            for kp in mod.knowledge_points:
                progress.knowledge_types[kp.id] = kp.type

    def advance_stage(
        self, progress: LearningProgress, next_stage: LearningStage
    ) -> None:
        progress.current_stage = next_stage
        progress.updated_at = time.time()

    def record_quiz_attempt(
        self, progress: LearningProgress, attempt: QuizAttempt
    ) -> None:
        key = (attempt.question_id, attempt.knowledge_point_id)

        if not attempt.is_correct and attempt.error_type is not None:
            # Find existing error record for this question + knowledge point.
            existing = None
            for rec in progress.error_records:
                if rec.question_id == attempt.question_id and rec.knowledge_point_id == attempt.knowledge_point_id:
                    existing = rec
                    break

            if existing is not None:
                existing.retry_history.append(
                    RetryAttempt(
                        timestamp=time.time(),
                        is_correct=False,
                        attempt_number=len(existing.retry_history) + 1,
                    )
                )
                existing.status = "retrying"
            else:
                record = ErrorRecord(
                    id=uuid.uuid4().hex,
                    question_id=attempt.question_id,
                    knowledge_point_id=attempt.knowledge_point_id,
                    module_id=attempt.module_id,
                    error_type=attempt.error_type,
                    self_attribution=attempt.self_attribution,
                    status="active",
                )
                progress.error_records.append(record)

        elif attempt.is_correct:
            # Graduate any active error record for this question + knowledge point.
            for rec in progress.error_records:
                if (
                    rec.question_id == attempt.question_id
                    and rec.knowledge_point_id == attempt.knowledge_point_id
                    and rec.status in ("active", "retrying")
                ):
                    rec.retry_history.append(
                        RetryAttempt(
                            timestamp=time.time(),
                            is_correct=True,
                            attempt_number=len(rec.retry_history) + 1,
                        )
                    )
                    rec.status = "graduated"
                    break

        progress.updated_at = time.time()

    def update_mastery(
        self, progress: LearningProgress, kp_id: str, level: float
    ) -> None:
        progress.mastery_levels[kp_id] = level
        progress.updated_at = time.time()

    def save(self, progress: LearningProgress) -> None:
        self._store.save(progress)


__all__ = ["LearningService"]
