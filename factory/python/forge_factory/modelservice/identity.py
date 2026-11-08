"""Factory-side access to the served-model identity contract (feature 017). The implementation lives in the
factory-agnostic model tier; the factory may depend on this shared contract and nothing else from the model side."""
from model_tier.identity import (  # noqa: F401
    FIELDS,
    IdentityError,
    build,
    file_entries,
    fingerprint,
    fingerprint_entries,
    from_lock,
    inferred_from_models_endpoint,
    require_match,
    sha,
    short,
    validate,
    verify,
)
