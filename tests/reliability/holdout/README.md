# CRE holdout set (protected: tests/reliability/**)
Independent regression fixtures that candidates and repair agents may not read-write through their grants; changes
are oracle changes and need their own commit and a new baseline comparison (ADR-CRE-004). The runner verifies every
file hash against holdout/suite.yaml before running.
