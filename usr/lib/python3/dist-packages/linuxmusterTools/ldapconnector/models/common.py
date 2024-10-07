from dataclasses import dataclass, asdict


@dataclass
class LMNParent:
    """
    Common parent class to gather common methods.
    """

    def asdict(self):
        return asdict(self)

