class SchoolError(Exception):
    """
    Raised when an operation is given an invalid or unresolvable school scope,
    e.g. 'global' where a single, concrete school is required.
    """
