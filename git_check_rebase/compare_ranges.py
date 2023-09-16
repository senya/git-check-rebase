import re

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any, Tuple, Dict

from .simple_git import git_log_table, git
from .compare_commits import are_commits_equal
from .check_rebase_meta import subject_to_key, text_add_indent, Meta, \
    CommitMeta

from .viewable import Span, GitHashCell, CompRes, VTable, VTableRow
from .parse_issues import parse_issues


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
    in_tag: str


def git_log_commits(git_range):
    res = []
    for h, ad, an, d, s in git_log_table('%h %ad %an %D %s', git_range):
        tag = ''
        if 'tag:' in d:
            desc = next(x for x in d.split(',')
                        if x.strip().startswith('tag:'))
            tag = desc.split(':', 1)[1].strip()
            if not re.fullmatch(r'v([0-9]+\.)*[0-9]+', tag):
                tag = None
        res.append(Commit(commit_hash=h, author_date=ad,
                          author_name=an, subject=s, in_tag=tag))

    current_tag = ''
    for c in reversed(res):
        if c.in_tag:
            current_tag = c.in_tag
            continue

        if current_tag:
            c.in_tag = current_tag

    return res


class MultiRange:
    """ Class maintains multiple git ranges """
    def __init__(self, definition, meta=None, default_base=None):
        if ':' in definition:
            self.name, definition = definition.split(':', 1)
            self.legend = f'{self.name} = {definition}'
        else:
            self.name = definition.replace('.', '-').replace('/', '-')
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
    issues: List[Any]
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
        self.msg_issues = list(set(re.findall(r'\b[A-Z]+-\d+\b(?!-)', msg)))
        self.msg_issues.sort(key=lambda x: int(x.split('-', 1)[1]))

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

        if self.new_ind != -1 and not out[self.new_ind]:
            out[self.new_ind] = Span('███???███', 'unknown')

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

    def all_ok(self) -> bool:
        return all(c is not None and c.comp != CompRes.NONE
                   for c in self.commits)

    def all_equal(self) -> bool:
        return all(c is not None and
                   c.comp in (CompRes.BASE, CompRes.EQUAL)
                   for c in self.commits)

    def match_filter(self, expr: str) -> bool:
        if not expr:
            return True
        commits = self.get_commits()
        env = {a: getattr(self, a) for a in dir(self) if a[0] != '_'}
        for i, r in enumerate(self.ranges):
            if r.name.isidentifier():
                env[r.name] = commits[i]
        return eval(expr, env)


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
                    in_tag = ''
                    if r_ind in (row.up_ind, row.new_ind):
                        in_tag = c2.in_tag
                    row.commits[r_ind] = GitHashCell(c2.commit_hash,
                                                     in_tag=in_tag)
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

    def add_porting_issues(self, issue_tracker, porting_issues):
        if issue_tracker == 'jira':
            from .gcr_jira import GCRTracer
        else:
            import importlib
            mod, klass = issue_tracker.rsplit('.', 1)
            GCRTracer = getattr(importlib.import_module(mod), klass)

        tracker = GCRTracer()
        issues_map = parse_issues(tracker, porting_issues,
                                  [r.subject for r in self.rows])
        for row in self.rows:
            issues = issues_map.get(row.subject)
            if issues:
                row.issues = issues

    def to_list(self, columns: List[Column],
                fmt: str = 'colored',
                headers: bool = True,
                rows_hide_level: RowsHideLevel = RowsHideLevel.SHOW_ALL,
                rows_filter: str = '') -> VTable:

        out: VTable = []
        line: VTableRow

        if headers:
            line = [c.name for c in columns]
            if 'COMMITS' in line:
                i = line.index('COMMITS')
                line[i:i+1] = [r.name for r in self.ranges]
            out.append(line)

        index_len = len(str(len(self.rows)))

        for row_ind, row in enumerate(self.rows):
            if not row.match_filter(rows_filter):
                continue

            if rows_hide_level.value >= RowsHideLevel.HIDE_CHECKED.value and \
                    row.all_ok():
                continue
            if rows_hide_level.value >= RowsHideLevel.HIDE_EQUAL.value and \
                    row.all_equal():
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
