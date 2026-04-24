from ._base import Datatype


class ReportMessage(Datatype):
    """Message container for a report.

    Attributes:
        report_code (int): integer report code, interpreted by the backend
    """

    report_code: int
