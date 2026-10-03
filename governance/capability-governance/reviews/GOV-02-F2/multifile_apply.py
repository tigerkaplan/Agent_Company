"""Probe effect loss between two actual controlled target mutations."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from runtime.core import capability_governance as gov
from runtime.tests.test_actions import ControlledWriteTests,MutatingAdapter

f=ControlledWriteTests();f.setUp()
try:
    request=f.request();store,_,_=gov._DISPATCH.get()
    writes=[];original=f.runtime._atomic_write
    def observed_write(path,contents):
        original(path,contents)
        if f.target in path.parents:
            writes.append(str(path.relative_to(f.target)))
            if len(writes)==1:
                for suffix in ('anchor','witness'):
                    store._decision_path(request.execution_id,'effect-controlled_write',suffix).unlink()
    def mutate(workspace):
        (workspace/'src'/'new.txt').write_text('first-mutation')
        (workspace/'src'/'existing.txt').write_text('second-mutation')
    denied=False;error=None;status=None;outcome=None
    with patch.object(f.runtime,'_atomic_write',side_effect=observed_write):
        try:
            outcome=f.execute_controlled(MutatingAdapter(mutate),request)
            status=outcome.provider_result.status
        except ValueError as exc:denied=True;error=str(exc)
    acceptance_denied=None;acceptance_error=None
    if outcome is not None:
        from runtime.execution.models import ExecutionResult
        result=ExecutionResult(execution_id=request.execution_id,job_id=request.job_id,status='needs_review',
            output_refs=(outcome.artifact_ref,),summary='Independent multi-file apply observation',error=None,
            provider=None,started_at='2026-10-03T00:00:00Z',completed_at='2026-10-03T00:00:00Z',
            execution_mode='CONTROLLED_WRITE',dry_run=False)
        try:
            store.create(request,result)
            store.load(request.execution_id,require_authority=True)
            acceptance_denied=False
        except ValueError as exc:acceptance_denied=True;acceptance_error=str(exc)
    observation=dict(denied=denied,error=error,provider_status=status,target_write_order=writes,
        existing_target_contents=(f.target/'src'/'existing.txt').read_text(),
        effect_pair_missing=not store._decision_path(request.execution_id,'effect-controlled_write','anchor').exists(),
        new_target_exists=(f.target/'src'/'new.txt').exists(),
        canonical_result_acceptance_denied=acceptance_denied,acceptance_error=acceptance_error)
    (Path(__file__).resolve().parent/'multifile-apply-observations.json').write_text(json.dumps(observation,indent=2)+'\n')
    print(json.dumps(observation,indent=2))
    sys.exit(1 if len(writes)>1 and not denied else 0)
finally:f.tearDown()
