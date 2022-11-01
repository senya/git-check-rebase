import re

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any, Union, Tuple, Dict

from .simple_git import git_log_table, git
from .compare_commits import are_commits_equal
from .check_rebase_meta import subject_to_key, text_add_indent, Meta, \
    CommitMeta

from .viewable import Span, Issue, GitHashCell, CompRes, VTable


def parse_jira_issue(jira_issue: Any) -> Issue:
    return Issue(key = jira_issue.key,
                 critical = jira_issue.fields.priority.name in ('Critical',
                                                                'Blocker'),
                 fixed = jira_issue.fields.resolution and
                    jira_issue.fields.resolution.name == 'Fixed')


class NoBaseError(Exception):
    pass


MINUS_REGEX = re.compile(r'([^^~]+)(\^\d*|~\d*)+-')


def parse_range(definition: str, default_base: Optional[str] = None) -> \
        Tuple[str, str]:
    """Parse one git range
    Supported definitions:

    <commit>             -> (commit~, commit)

    ..<commit>           -> (default_base, commit)
                            default_base must not be None in this case

    <commit1>..<commit2> -> (commit1, commit2)

    <commit>..           -> (commit, 'HEAD')

    <hash>~5-            -> (hash~5, hash)
      and a lot of similar things, you may use tag/branch name instead of hash
      and any combination of ~ and ^ operators
    """

    assert definition
    assert ',' not in definition
    assert ':' not in definition

    m = MINUS_REGEX.fullmatch(definition)
    if m is not None:
        return definition[:-1], m.group(1)

    if '..' not in definition:
        return definition + '~', definition

    base, top = definition.split('..')

    if not base:
        if not default_base:
            raise NoBaseError
        base = default_base
    if not top:
        top = 'HEAD'

    if not base:
        raise NoBaseError

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


class MultiRange:
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
            self.commits.extend(git_log_commits(f'{base}..{top}'))

        self.by_key = {}
        for i, c in enumerate(self.commits):
            key = subject_to_key(c.subject, meta)
            self.by_key[key] = i, c


class Column(Enum):
    INDEX = 1
    FEATURE = 2
    COMMITS = 3
    CHERRY = 4
    DATE = 5
    AUTHOR = 6
    MSG_ISSUES = 7
    SUBJECT = 8

class Row:
    """Representation of on row if git-range-diff-table"""
    commits: List[Optional[GitHashCell]]
    issues: List[Issue]
    date: str
    author: str
    subject: str
    _meta: Optional[Meta]
    _key: str

    def __init__(self, ranges, ind, meta):
        c = ranges[-1].commits[ind]

        self.up_ind = -1
        self.new_ind = -1
        for i, r in enumerate(ranges):
            if r.name == 'up':
                self.up_ind = i
            elif r.name == 'new':
                self.new_ind = i

        self.ranges = ranges
        self.commits = \
            [None] * (len(ranges) - 1) + [GitHashCell(c.commit_hash)]
        self.issues = []
        self.date = c.author_date
        self.author = c.author_name
        self.subject = c.subject
        self._meta = meta
        self._key = subject_to_key(c.subject, meta)

        msg = git(f'log -1 {c.commit_hash}')
        self.cherry = 'cherry picked' in msg
        self.msg_issues = re.findall(r'\b[A-Z]+-\d+\b', msg)

        m = re.search(r'^    Feature: (.*)$', msg, re.MULTILINE)
        if m:
            self.feature = m.group(1)
        else:
            self.feature = self.meta.feature if self.meta else None

        m = re.search(r'^    Upstreaming: (.*)$', msg, re.MULTILINE)
        if m:
            self.upstreaming = m.group(1)
        else:
            self.upstreaming = self.meta.upstreaming if self.meta else None

    def get_comment(self) -> str:
        return '' if self.meta is None else self.meta.comment

    @property
    def meta(self) -> Optional[CommitMeta]:
        if self._meta is None:
            return None
        return self._meta.by_key.get(self._key)

    def get_commits(self):
        out = self.commits[:]

        if self.up_ind != -1 and out[self.up_ind] is None \
                and self.upstreaming:
            out[self.up_ind] = self.upstreaming

        if self.meta and self.meta.drop:
            sp = Span(self.meta.drop, 'drop')
            if self.new_ind != -1 and out[self.new_ind] is None:
                out[self.new_ind] = sp
            elif self.up_ind != -1 and out[self.up_ind] is None:
                out[self.up_ind] = sp

        if self.new_ind != -1 and out[self.new_ind] is None:
            out[self.new_ind] = self.issues

        return out

    def to_list(self, columns: List[Column],
                default: Dict[Column, Any]) -> List[Any]:

        line = []
        for c in columns:
            if c == Column.FEATURE:
                line.append(self.feature)
            elif c == Column.COMMITS:
                line.extend(self.get_commits())
            elif c == Column.DATE:
                line.append(self.date)
            elif c == Column.AUTHOR:
                line.append(self.author)
            elif c == Column.SUBJECT:
                line.append(self.subject)
            elif c == Column.MSG_ISSUES:
                line.append(self.msg_issues)
            elif c == Column.CHERRY:
                line.append('V' if self.cherry else None)
            else:
                line.append(default[c])
        return line


class RowsHideLevel(Enum):
    SHOW_ALL = 1
    HIDE_EQUAL = 2
    HIDE_CHECKED = 3


class Table:
    def __init__(self, ranges: List[MultiRange],
                 meta: Optional[Meta] = None) -> None:
        """Prepare table with commits found by subjects using @meta info.
        Link with @meta elements. (Modifying separate CommitMeta objects is OK,
        but if you update @meta significantly, regenerated the table)
        No comparison is done yet.
        """

        self.meta = meta
        self.ranges = ranges
        self.rows = []

        corresponding = [len(r.commits) == len(ranges[-1].commits)
                         for r in ranges[:-1]]

        for i, c in enumerate(ranges[-1].commits):
            an = c.author_name
            if an == 'Vladimir Sementsov-Ogievskiy':  # too long :)
                an = "Vladimir S-O"

            key = subject_to_key(c.subject, meta)
            row = Row(ranges, i, meta)

            for r_ind, r in enumerate(ranges[:-1]):
                if key in r.by_key:
                    j, c2 = r.by_key[key]
                    row.commits[r_ind] = GitHashCell(c2.commit_hash)
                    if j != i:
                        corresponding[r_ind] = False

            self.rows.append(row)

        # If user cares to pass ranges of same length, and all found commits
        # have same index in range as corresponding commit in last range,
        # assume that non-found commits are just renamed but stay at same
        # position.
        for i in range(len(ranges) - 1):
            if not corresponding[i]:
                continue

            for j, row in enumerate(self.rows):
                if row.commits[i] is None:
                    c = ranges[i].commits[j]
                    row.commits[i] = GitHashCell(c.commit_hash)

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
        from .parse_jira import parse_jira

        auth, server = jira.rsplit('@', 1)
        user, password = auth.split(':', 1)
        jiramap = parse_jira('https://' + server, user, password, jira_issues,
                             [r.subject for r in self.rows])

        for row in self.rows:
            issues = jiramap.get(row.subject)
            if issues:
                row.issues = [parse_jira_issue(issue) for issue in issues]

    def to_list(self, columns: List[Column],
                fmt: str = 'colored',
                headers: bool = True,
                rows_hide_level: RowsHideLevel = RowsHideLevel.SHOW_ALL) \
            -> VTable:

        out: VTable = []
        line: VTableRow

        if headers:
            line = [c.name for c in columns]
            if 'COMMITS' in line:
                i = line.index('COMMITS')
                line[i : i + 1] = [r.name for r in self.ranges]
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

            line = row.to_list(columns, {
                Column.INDEX: f'{row_ind + 1:0{index_len}}'
            })

            out.append(line)
            if row.meta and row.meta.comment:
                line = [None] * len(line)
                line[-1] = text_add_indent(row.meta.comment, 2)
                out.append(line)

        return out
