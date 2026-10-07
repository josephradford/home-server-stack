class OddJobsError(Exception):
    """Base class for expected failures (bad config, source changed, etc.)."""


class ConfigError(OddJobsError):
    pass


class AdapterError(OddJobsError):
    pass
