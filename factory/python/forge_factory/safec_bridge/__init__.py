"""Feature 011: the public Forge-C side of the SafeC Forge bridge (ADR-0015).

SafeC Forge is a separate private product. This package holds only what public Forge-C needs: the frozen wire
contracts (specs/011-safec-semantic-first/contracts), strict parsing and identity checks, bounded invocation of a
pinned local executable, and the public/private boundary checks. It never vendors SafeC source, never treats a SafeC
check result as a phase or release decision, and never calls a network service.
"""
