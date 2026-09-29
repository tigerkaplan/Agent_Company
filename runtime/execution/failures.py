"""Typed trusted execution failures; never inferred from provider output."""

from runtime.actions.models import ScopeContractError
from runtime.actions.store import MutationArtifactError
from runtime.approvals.models import ApprovalContractError
from runtime.approvals.runtime import ApprovalRuntimeError
from runtime.approvals.store import ApprovalStoreError
from runtime.budget.models import BudgetContractError
from runtime.budget.store import ExecutionBudgetStoreError
from runtime.continuation.models import ContinuationContractError
from runtime.continuation.store import AuthorizedPlanStoreError
from runtime.core.jobs import RuntimeError as JobRuntimeError
from runtime.core.references import ReferenceResolutionError
from runtime.core.validation import JobValidationError
from runtime.execution.models import ExecutionContractError
from runtime.execution.validation import ExecutionResultValidationError
from runtime.providers.artifacts import ProviderArtifactError
from runtime.providers.config import ProviderConfigError
from runtime.providers.context import ContextBuildError
from runtime.retry.models import RetryContractError
from runtime.retry.store import RetryStoreError
from runtime.review.models import ReviewContractError
from runtime.review.runtime import ReviewRuntimeError
from runtime.review.store import ReviewStoreError
from runtime.storage.execution_store import ExecutionStoreError
from runtime.storage.file_store import JobStoreError


INTEGRITY_FAILURES = (
    ExecutionContractError, ExecutionResultValidationError, JobValidationError,
    ExecutionStoreError, JobStoreError, RetryStoreError, ProviderArtifactError,
    MutationArtifactError, ApprovalStoreError, ApprovalContractError,
    ReviewStoreError, ReviewContractError, AuthorizedPlanStoreError,
    ExecutionBudgetStoreError,
)
AUTHORITY_FAILURES = (
    ScopeContractError, JobRuntimeError, ApprovalRuntimeError, ReviewRuntimeError,
)
POLICY_FAILURES = (
    ProviderConfigError, ContextBuildError, RetryContractError,
    ContinuationContractError, BudgetContractError, ReferenceResolutionError,
)
TRUSTED_EXECUTION_FAILURES = INTEGRITY_FAILURES + AUTHORITY_FAILURES + POLICY_FAILURES
