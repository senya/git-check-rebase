from enum import Enum
from dataclasses import dataclass
from typing import List, Any, Union


@dataclass
class Span:
    text: str
    klass: str

    def __str__(self):
        return self.text


class CompRes(Enum):
    NONE = 1
    BASE = 2  # Some other cells are equal to this one
    EQUAL = 3  # Equal to base, auto-checked
    CHECKED = 4  # Equal to base, checked by hand


@dataclass
class GitHashCell:
    """Representation of one cell with commit hash"""
    commit_hash: str
    comp: CompRes = CompRes.NONE


Viewable = Union[None, str, Span, GitHashCell]
VTableCell = Union[str, Viewable, List[Viewable]]
VTableRow = List[VTableCell]
VTable = List[VTableRow]
ConvertedTable = List[List[str]]


class Viewer:
    list_splitter = ''

    def view_git_hash(self, h: GitHashCell) -> str:
        return h.commit_hash

    def view_span(self, s: Span) -> str:
        return s.text

    def view_converted_table(self, tab: ConvertedTable) -> str:
        raise NotImplementedError

    def view_element(self, el: Viewable) -> str:
        if type(el) == GitHashCell:
            return self.view_git_hash(el)

        if type(el) == Span:
            return self.view_span(el)

        if hasattr(el, 'is_critical'):
            return self.view_issue(el)

        if el is None:
            return ''

        return str(el)

    def convert_table(self, tab: VTable) -> ConvertedTable:
        out: ConvertedTable = []
        for row in tab:
            out.append([])
            for i, cell in enumerate(row):
                if isinstance(cell, list):
                    out[-1].append(
                        self.list_splitter.join(self.view_element(el)
                                                for el in cell))
                else:
                    out[-1].append(self.view_element(cell))
        return out

    def view_table(self, tab: VTable) -> str:
        out = self.convert_table(tab)
        return self.view_converted_table(out)

    def view_issue(self, issue: Any) -> str:
        if issue.is_fixed():
            klass = 'bug-fixed'
        elif issue.is_critical():
            klass = 'bug-critical'
        else:
            klass = 'bug'
        return self.view_span(Span(issue.key, klass))
