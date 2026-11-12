def validate_configuration(value, expected_sources):
    if not isinstance(value, dict) or not isinstance(expected_sources, dict):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")

    required_fields = {"source_sha256", "soak_source_sha256", "campaign_source_sha256", "interval_seconds", "max_samples", "minimum_free_bytes"}
    if set(value.keys()) != required_fields:
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")

    expected_keys = {"source_sha256", "soak_source_sha256", "campaign_source_sha256"}
    if set(expected_sources.keys()) != expected_keys:
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")

    hex_pattern = r'^[0-9a-f]{64}$'
    for key in expected_keys:
        val = expected_sources[key]
        if not isinstance(val, str) or not re.fullmatch(hex_pattern, val):
            raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
        if value[key] != val:
            raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")

    interval = value["interval_seconds"]
    if isinstance(interval, bool) or not isinstance(interval, int):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
    if not (5 <= interval <= 600):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")

    max_samp = value["max_samples"]
    if isinstance(max_samp, bool) or not isinstance(max_samp, int):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
    if not (1 <= max_samp <= 50000):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")

    min_free = value["minimum_free_bytes"]
    if isinstance(min_free, bool) or not isinstance(min_free, int):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")
    min_val = 64 * 1024 * 1024
    max_val = 2**63 - 1
    if not (min_val <= min_free <= max_val):
        raise Refused("OPERATIONAL_COLLECTION_CONFIGURATION_INVALID")

    return dict(value)
