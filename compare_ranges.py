import sys

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any, Union

from parse_jira import parse_jira
from simple_git import git_log_table
from compare_commits import are_commits_equal
from check_rebase_meta import subject_to_key, text_add_indent, Meta, CommitMeta
from span import Span


class TableIssue:
    def __init__(self, jira_issue: Any) -> None:
        self.key = jira_issue.key
        self.critical = jira_issue.fields.priority.name in ('Critical',
                                                            'Blocker')
        self.fixed = jira_issue.fields.resolution and \
            jira_issue.fields.resolution.name == 'Fixed'

    def to_span(self, fmt: str = 'colored') -> Span:
        if self.fixed:
            klass = 'bug-fixed'
        elif self.critical:
            klass = 'bug-critical'
        else:
            klass = 'bug'
        return Span(self.key, fmt, klass)


class CommitRange:
    def __init__(self, definition, meta=None):
        if ':' in definition:
            self.name, self.git_range = definition.split(':', 1)
        else:
            self.name = definition
            self.git_range = definition

        if '..' in self.git_range:
            self.base, self.top = self.git_range.split('..', 1)
            if self.top == '':
                self.top = 'HEAD'
        else:
            self.top = self.git_range
            self.base = None

        lines = git_log_table('%h %s', self.git_range)

        self.by_key = {}
        for line in lines:
            try:
                h, s = line
            except ValueError:
                print(line)
                sys.exit(0)
            key = subject_to_key(s, meta)

            self.by_key[key] = h


class ComparisonResult(Enum):
    NONE = 1
    BASE = 2  # Some other cells are equal to this one
    EQUAL = 3  # Equal to base, auto-checked
    CHECKED = 4  # Equal to base, checked by hand


@dataclass
class GitHashCell:
    """Representation of one cell with commit hash"""
    commit_hash: str
    comp: ComparisonResult = ComparisonResult.NONE

    def to_span(self, fmt: str = 'colored') -> Span:
        return Span(self.commit_hash, fmt, self.comp.name.lower())


@dataclass
class Row:
    """Representation of on row if git-range-diff-table"""
    commits: List[Optional[GitHashCell]]
    issues: List[TableIssue]
    date: str
    author: str
    subject: str
    meta: Optional[CommitMeta] = None

    def get_comment(self) -> str:
        return '' if self.meta is None else self.meta.comment


SpanTableCell = Union[None, str, Span]
SpanTableRow = List[SpanTableCell]
SpanTable = List[SpanTableRow]


class Table:
    def __init__(self, ranges: List[CommitRange],
                 meta: Optional[Meta] = None) -> None:
        """Prepare table with commits found by subjects using @meta information.
        Link with @meta elements. (Modifying separate CommitMeta objects is OK,
        but if you update @meta significantly, regenerated the table)
        No comparison is done yet.
        """

        self.meta = meta
        self.ranges = ranges
        self.rows = []

        git_range = ranges[-1].git_range
        for h, ad, an, s in git_log_table('%h %ad %an %s', git_range):
            if an == 'Vladimir Sementsov-Ogievskiy':  # too long :)
                an = "Vladimir S-O"

            row = Row(commits=[], issues=[], date=ad, author=an, subject=s)

            key = subject_to_key(s, meta)
            for r in ranges[:-1]:
                if key in r.by_key:
                    row.commits.append(GitHashCell(r.by_key[key]))
                else:
                    row.commits.append(None)

            row.commits.append(GitHashCell(h))

            if meta is not None:
                row.meta = meta.by_key.get(key)

            self.rows.append(row)

    def _compare_commits(self, base: GitHashCell, other: GitHashCell,
                         row_meta: Optional[CommitMeta],
                         ign_cmsg: bool) -> None:
        if are_commits_equal(base.commit_hash, other.commit_hash, ign_cmsg):
            other.comp = ComparisonResult.EQUAL
            base.comp = ComparisonResult.BASE
            return

        if row_meta is None:
            return

        for a, b in row_meta.checked:
            for x, y in ((a, b), (b, a)):
                if are_commits_equal(x, other.commit_hash, ign_cmsg) and \
                        are_commits_equal(y, base.commit_hash, ign_cmsg):
                    other.comp = ComparisonResult.CHECKED
                    base.comp = ComparisonResult.BASE
                    return

    def do_comparison(self, ignore_cmsg: bool) -> None:
        for row in self.rows:
            base_ind = len(row.commits) - 1 if row.commits[0] is None else 0
            base = row.commits[base_ind]
            assert base is not None

            for i, c in enumerate(row.commits):
                if c is None or i == base_ind:
                    continue

                self._compare_commits(base, c, row.meta, ignore_cmsg)

    def add_jira_info(self, jira, jira_issues):
        auth, server = jira.rsplit('@', 1)
        user, password = auth.split(':', 1)
        jiramap = parse_jira('https://' + server, user, password, jira_issues,
                             [r.subject for r in self.rows])

        for row in self.rows:
            issues = jiramap.get(row.subject)
            if issues:
                row.issues = [TableIssue(issue) for issue in issues]

    def to_spans(self, fmt: str = 'colored',
                 headers: bool = True,
                 date_column: bool = True,
                 author_column: bool = True,
                 meta_column: bool = True,
                 rows_full: bool = True) -> SpanTable:

        out: SpanTable = []
        line: SpanTableRow

        if headers:
            line = ['<tag>'] if meta_column else []
            line += [r.name for r in self.ranges]
            if date_column:
                line.append('DATE')
            if author_column:
                line.append('AUTHOR')
            line.append('SUBJECT')
            out.append(line)

        for row in self.rows:
            if not rows_full and \
                    all(c is not None and c.comp != ComparisonResult.NONE for
                        c in row.commits):
                continue

            line = []
            if meta_column:
                meta = []
                if row.meta and row.meta.tag:
                    klass = 'drop' if row.meta.tag.startswith('drop') else None
                    meta.append(Span(row.meta.tag, fmt, klass))
                meta += [issue.to_span() for issue in row.issues]

                line.append(' '.join(map(str, meta)))

            for commit in row.commits:
                if commit is None:
                    line.append(None)
                else:
                    line.append(commit.to_span())

            if date_column:
                line.append(row.date)
            if author_column:
                line.append(row.author)
            line.append(row.subject)

            if meta_column and line[0] is None and \
                    all(c is None for c in row.commits[:-1]):
                line[0] = Span('???', fmt, 'unknown')

            out.append(line)
            if row.meta and row.meta.comment:
                line = [None] * len(line)
                line[-1] = text_add_indent(row.meta.comment, 2)
                out.append(line)

        return out
