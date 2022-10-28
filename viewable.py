from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any, Union, Tuple, Dict


@dataclass
class Span:
    text: str
    klass: str

    def __str__(self):
        return self.text


@dataclass
class Issue:
    key: str
    critical: bool
    fixed: bool


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

Viewable = Union[None, str, Span, Issue, GitHashCell]
VTableCell = Union[Viewable, List[Viewable]]
VTableRow = List[VTableCell]
VTable = List[VTableRow]


class Viewer:
    list_splitter = ''

    def view_git_hash(self, h: GitHashCell) -> str:
        return h.commit_hash

    def view_element(self, el: Viewable) -> str:
        if type(el) == GitHashCell:
            return self.view_git_hash(el)

        if type(el) == Span:
            return self.view_span(el)

        if el is None:
            return ''

        return str(el)

    def convert_table(self, tab):
        out = []
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

    def view_table(self, tab):
        out = self.convert_table(tab)
        return self.view_converted_table(out)
