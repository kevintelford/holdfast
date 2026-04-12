"""holdfast: Stable outcomes, smarter prompts."""

from .contract import Contract, EvolvableRef
from .detect import Alert, check_contract
from .evidence import log_run, track
from .evolve import EvolutionProposal, build_evolution_prompt, propose_evolution
from .validate import ValidationResult, validate_output
from .version import apply_evolution, list_versions, rollback

__all__ = [
    "Alert",
    "Contract",
    "EvolvableRef",
    "EvolutionProposal",
    "ValidationResult",
    "apply_evolution",
    "build_evolution_prompt",
    "check_contract",
    "list_versions",
    "log_run",
    "propose_evolution",
    "rollback",
    "track",
    "validate_output",
]
