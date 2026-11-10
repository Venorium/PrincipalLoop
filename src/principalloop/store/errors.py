"""Stable errors of the persistence boundary."""


class StoreError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")
