from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any, Union, Tuple

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


def parse_range(definition: str, default_base: Optional[str] = None) -> \
        Tuple[Optional[str], str]:
    """Parse one git range
    Supported definitions:

    <commit>             -> (default_base, commit)

    <commit1>..<commit2> -> (commit1, commit2)

    <commit>..           -> (commit, 'HEAD')
    """

    assert definition
    assert ',' not in definition
    assert ':' not in definition

    base: Optional[str]
    if '..' in definition:
        base, top = definition.split('..', 1)
        if top == '':
            top = 'HEAD'
    else:
        top = definition
        base = default_base

    return base, top


@dataclass
class Commit:
    commit_hash: str
    author_date: str
    author_name: str
    subject: str


def git_log_commits(git_range):
    return [Commit(commit_hash=h, author_date=ad,
                   author_name=an, subject=s) for h, ad, an, s in
            git_log_table('%h %ad %an %s', git_range)]


class CommitRange:
    """ Class maintains multiple git ranges """
    def __init__(self, definition, meta=None, default_base=None):
        if ':' in definition:
            self.name, definition = definition.split(':', 1)
            self.legend = f'{self.name} = {definition}'
        else:
            self.name = definition
            self.legend = None

        if ',' in definition:
            # base and top are not defined for several ranges
            self.base = self.top = None
        else:
            self.base, self.top = parse_range(definition, default_base)

        self.commits = []
        for rng in definition.split(','):
            base, top = parse_range(rng, default_base)
            # We should never work with the whole branch, it is slow.
            assert base is not None
            self.commits.extend(git_log_commits(f'{base}..{top}'))

        self.by_key = {}
        for c in self.commits:
            key = subject_to_key(c.subject, meta)
            self.by_key[key] = c.commit_hash


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
    _meta: Optional[Meta]
    _key: str

    def get_comment(self) -> str:
        return '' if self.meta is None else self.meta.comment

    @property
    def meta(self) -> Optional[CommitMeta]:
        if self._meta is None:
            return None
        return self._meta.by_key.get(self._key)


class RowsHideLevel(Enum):
    SHOW_ALL = 1
    HIDE_EQUAL = 2
    HIDE_CHECKED = 3


SpanTableCell = Union[None, str, Span]
SpanTableRow = List[SpanTableCell]
SpanTable = List[SpanTableRow]


class Table:
    def __init__(self, ranges: List[CommitRange],
                 meta: Optional[Meta] = None) -> None:
        """Prepare table with commits found by subjects using @meta info.
        Link with @meta elements. (Modifying separate CommitMeta objects is OK,
        but if you update @meta significantly, regenerated the table)
        No comparison is done yet.
        """

        self.meta = meta
        self.ranges = ranges
        self.rows = []

        for c in ranges[-1].commits:
            an = c.author_name
            if an == 'Vladimir Sementsov-Ogievskiy':  # too long :)
                an = "Vladimir S-O"

            key = subject_to_key(c.subject, meta)
            row = Row(commits=[], issues=[], date=c.author_date, author=an,
                      subject=c.subject, _meta=meta, _key=key)

            for r in ranges[:-1]:
                if key in r.by_key:
                    row.commits.append(GitHashCell(r.by_key[key]))
                else:
                    row.commits.append(None)

            row.commits.append(GitHashCell(c.commit_hash))

            self.rows.append(row)

    @staticmethod
    def _compare_commits(base: GitHashCell, other: GitHashCell,
                         row_meta: Optional[CommitMeta],
                         ign_cmsg: bool) -> None:
        if are_commits_equal(base.commit_hash, other.commit_hash, ign_cmsg):
            other.comp = CompRes.EQUAL
            base.comp = CompRes.BASE
            return

        if row_meta is None:
            return

        for a, b in row_meta.checked:
            for x, y in ((a, b), (b, a)):
                if are_commits_equal(x, other.commit_hash, ign_cmsg) and \
                        are_commits_equal(y, base.commit_hash, ign_cmsg):
                    other.comp = CompRes.CHECKED
                    base.comp = CompRes.BASE
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
                 index_column: bool = False,
                 commits_columns: bool = True,
                 rows_hide_level: RowsHideLevel = RowsHideLevel.SHOW_ALL) \
            -> SpanTable:

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

        index_len = len(str(len(self.rows)))

        for row_ind, row in enumerate(self.rows):
            if rows_hide_level.value >= RowsHideLevel.HIDE_CHECKED.value and \
                    all(c is not None and c.comp != CompRes.NONE for
                        c in row.commits):
                continue
            if rows_hide_level.value >= RowsHideLevel.HIDE_EQUAL.value and \
                    all(c is not None and
                        c.comp in (CompRes.BASE, CompRes.EQUAL) for
                        c in row.commits):
                continue

            line = []
            if index_column:
                line.append(f'{row_ind + 1:0{index_len}}')
            if meta_column:
                meta = []
                if row.meta and row.meta.tag:
                    klass = 'drop' if row.meta.tag.startswith('drop') else None
                    meta.append(Span(row.meta.tag, fmt, klass))
                meta += [issue.to_span() for issue in row.issues]

                line.append(' '.join(map(str, meta)))

            if commits_columns:
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
