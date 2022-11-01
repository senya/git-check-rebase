import re
import os
import subprocess
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Tuple
from tempfile import mkstemp

from .simple_git import git, git_get_git_dir, git_log1, git_log

eat_numbers_subs = tuple((re.compile(a, re.MULTILINE), b) for a, b in
                         (
                             (r'\AFrom .*', 'From <from line>'),
                             (r'^index .*', 'index <some index>'),
                             (r'^commit .*', 'commit <some commit>'),
                             (r'^Date:.*00', 'Date: <some date>'),
                             (r'^@@ .* @@', '@@ <some lines> @@'),
                         ))

empty_line_changes_subs = tuple((re.compile(a, re.MULTILINE), b) for a, b in
                                (
                                    (r'^\+\n', ''),
                                    (r'^\-\n', ''),
                                ))


def eat_numbers(patch, ignore_empty_lines=True):
    for e in eat_numbers_subs:
        patch = e[0].sub(e[1], patch)

    if ignore_empty_lines:
        for e in empty_line_changes_subs:
            patch = e[0].sub(e[1], patch)

    return patch


def sorted_pair(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a <= b else (b, a)


class IsEqual(Enum):
    EQUAL = 1  # commits are equal, commit messages may differ
    DIFFERS = 2  # commits are different
    FULL_EQUAL = 3  # commits are equal as well as commit messages


class EqualityCache:
    def __init__(self, fname: str) -> None:
        self._dict = {}
        self.fname = fname

        try:
            with open(fname) as f:
                for line in f:
                    h1, h2, result = line.strip().split(' ', 2)
                    self._dict[sorted_pair(h1, h2)] = IsEqual[result]
        except FileNotFoundError:
            pass
        except (KeyError, ValueError):
            # Most probably old format detected
            os.unlink(fname)

    def get(self, h1: str, h2: str) -> Optional[IsEqual]:
        return self._dict.get(sorted_pair(h1, h2))

    def add(self, h1: str, h2: str, equal: IsEqual) -> None:
        pair = sorted_pair(h1, h2)
        self._dict[pair] = equal

        with open(self.fname, 'a') as f:
            f.write('{} {} {}\n'.format(pair[0], pair[1], equal.name))


CACHE = EqualityCache(os.path.join(git_get_git_dir(), 'commit-equality-cache'))


def are_commits_equal(c1: str, c2: str, ignore_cmsg: bool) -> bool:
    """Compare commits
    With ignore_cmsg=True compare only code-changes of the commits.
    With ignore_cmsg=False compare code-changes and commit messages.
    Note that dates and authors are never compared.
    """
    if c1 == c2:
        return True

    e = CACHE.get(c1, c2)
    if e is None:
        c1_text = eat_numbers(git('show --format= ' + c1))
        c2_text = eat_numbers(git('show --format= ' + c2))

        if c1_text != c2_text:
            e = IsEqual.DIFFERS
        elif git_log1('%B', c1) == git_log1('%B', c2):
            e = IsEqual.FULL_EQUAL
        else:
            e = IsEqual.EQUAL

        CACHE.add(c1, c2, e)

    return e == IsEqual.FULL_EQUAL or \
        (ignore_cmsg and e == IsEqual.EQUAL)


@dataclass
class IntrCompRes:
    """Type of interactive_compare_commits result
    @equal: commits are equal, nothing to compare. Interactive vim was not
            started.
    @ok: user marked the commit pair as OK
    @stop: user requested stop of interactive processing
    @comment: an updated comment
    @new_c1, @new_c2: set if successfully rebased
    """
    equal: bool = False
    ok: bool = False
    stop: bool = False
    comment: str = ''
    new_c1: str = ''
    new_c2: str = ''


def run_vim(f1: str, f2: str, comment_path: Optional[str],
            meta_tab_opened: bool) -> IntrCompRes:
    """Run vim to compare files @f1 and @f2 and return error code
    @f1: path to file on the left side
    @f2: path to file on the right side
    @comment_path: if non-Null, add support of meta tab to edit @comment_path
                   file
    @meta_tab_opened: start with opened meta tab

    additional vim interface:
    :ok - save all, exit with code 200
          (this leads to marking commits as OK and continue interactive
          process)
    :meta - toggle meta window to edit comment

    also,
    on exit with code 0 (by :q or :wq, etc..) interactive process will be
        continued.
    on exit with any other code (not 0 and not 200, for example by :cq)
        interactive process will be stopped.

    Returns IntrCompRes, where only @ok and @stop may be set, @equal is
    always False and comment is ''
    """
    if comment_path is None:
        assert meta_tab_opened is False

    cmd = ['vim', f2, '-c', ':diffthis', '-c', f':vsp {f1}', '-c', ':diffthis']

    if comment_path is not None:
        cmd += ['-c', 'command GCheckRebaseToggleMeta '
                f'let nr = bufwinnr("{comment_path}") | '
                'if nr > 0 | '
                'exe nr . "wincmd w" | wq | '
                'else | '
                f'top split {comment_path} | resize 5 | '
                'endif',
                '-c', 'cnoreabbrev meta GCheckRebaseToggleMeta']
        if meta_tab_opened:
            cmd += ['-c', ':GCheckRebaseToggleMeta']

    cmd += ['-c', 'command GCheckRebaseOk wa! | cq 200',
            '-c', 'cnoreabbrev ok GCheckRebaseOk',
            '-c', 'command GCheckRebaseStop wa! | cq 201',
            '-c', 'cnoreabbrev stop GCheckRebaseStop',]

    cmd += ['-c', ':norm gg']

    code = subprocess.run(cmd, check=False).returncode
    return IntrCompRes(ok = code == 200, stop = code not in (0, 200))


def text_to_lines(text: str) -> List[str]:
    if not text:
        return []

    if text[-1] == '\n':
        text = text[:-1]

    return text.split('\n')


def compile_updated_patch(orig_patch, orig_filtered, updated_filtered):
    """Given original patch, original patch with some lines substituted by
    eat_numbers() and updated by user version of the latter thing, restore
    how original patch should look if apply same changes.
    """
    orig_lines = text_to_lines(orig_patch)
    orig_filtered_lines = text_to_lines(orig_filtered)
    updated_filtered_lines = text_to_lines(updated_filtered)

    nr = len(orig_lines)
    assert nr == len(orig_filtered_lines)

    split_indeces = (i for i in range(nr)
                     if orig_lines[i] != orig_filtered_lines[i])

    spl_ind = next(split_indeces, None)
    updated_lines = []
    for line in updated_filtered_lines:
        if spl_ind is not None and line == orig_filtered_lines[spl_ind]:
            updated_lines.append(orig_lines[spl_ind])
            spl_ind = next(split_indeces, None)
        else:
            updated_lines.append(line)

    if spl_ind is not None:
        raise ValueError

    return '\n'.join(updated_lines) + '\n'


def check_git_clean_branch() -> str:
    branch = git('branch --show-current').strip()
    if not branch:
        return ''

    diff = git('diff --shortstat HEAD').strip()
    if diff:
        return ''

    return branch


class TriWay(Enum):
    SKIP = 1
    STOP = 2
    RETRY = 3


@dataclass
class ApplyResult:
    action: TriWay
    new_hash: str = ''


def tri_way(problem: str, retry: bool = True,
            stop_help: str = '') -> ApplyResult:
    print('You have modified a patch, but we can not update it:', problem)
    print(f'You have {"three" if retry else "two"} choices:')
    print(f"{TriWay.SKIP.value}. skip: don't apply the changes, "
          "continue interactive process")
    print(f'{TriWay.STOP.value}. stop: stop the interactive process now.',
          stop_help)
    if retry:
        print(f'{TriWay.RETRY.value}. retry: review same commit again and '
              'fix your changes')

    expected = f'{TriWay.SKIP.value}, {TriWay.STOP.value}'
    if retry:
        expected += f', {TriWay.RETRY.value}'

    while True:
        print(f'What to do? [{expected}]: ', end='')
        ans = input()
        try:
            return ApplyResult(TriWay(int(ans)))
        except (KeyError, ValueError):
            pass


def apply_patch_changes(commit_hash: str, branch: str, orig_patch: str,
                        orig_filtered: str,
                        updated_filtered_fname: str) -> ApplyResult:
    with open(updated_filtered_fname) as f:
        updated_filtered = f.read()

    if updated_filtered == orig_filtered:
        return ApplyResult(TriWay.SKIP)

    if not branch or branch != check_git_clean_branch():
        return tri_way('git is unclean or not at branch', retry=False)

    commit_hash = git_log1('%h', commit_hash)
    if commit_hash not in git_log('%h', branch):
        return tri_way('you are trying to modify commit that is not in the '
                       'current branch')

    try:
        updated_patch = compile_updated_patch(orig_patch, orig_filtered,
                                              updated_filtered)
    except ValueError:
        return tri_way('unparseable changes in patch')

    try:
        # checkout prints a lot of information to stderr even on success
        git(f'checkout {commit_hash}^', stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return tri_way('git checkout failed', retry=False)

    try:
        git('am', input=updated_patch)
    except subprocess.CalledProcessError:
        w = tri_way('git am failed',
                    stop_help='You will be left in git-am session. '
                    f'Use "git am --abort", then "git checkout {branch}" '
                    'to rollback.')
        if w != TriWay.STOP:
            git('am --abort')
            git('checkout -')
        return w

    applied_hash = git_log1('%h', 'HEAD')
    git(f'checkout {branch}', stderr=subprocess.DEVNULL)
    try:
        git(f'rebase {applied_hash}')
    except subprocess.CalledProcessError:
        w = tri_way('git rebase failed',
                    stop_help='You will probably be in a git rebase '
                    'conflict. Use "git rebase --abort" to rollback.')
        if w != TriWay.STOP:
            git('rebase --abort')
        return w

    return ApplyResult(TriWay.SKIP, applied_hash)


def interactive_compare_commits(c1, c2, c1_branch, c2_branch,
                                c2_ind=None, comment=None):
    """
    @comment: if None, do simple comparison of two commits and nothing more.
              if str (may be empty), create also temporary file for the
              comment, so that user can modify the comment.
    @c1_branch: if not empty, modifying c1 commit is allowed in that c1_branch,
                which must be current branch.
    @c2_branch: similar for c2. @c1_branch and @c2_branch must not be non-empty
                in the same time
    """
    assert not (c1_branch and c2_branch)
    c1_orig = git('show --format=email ' + c1)
    c1_filtered = eat_numbers(c1_orig, ignore_empty_lines=False)
    c2_orig = git('show --format=email ' + c2)
    c2_filtered = eat_numbers(c2_orig, ignore_empty_lines=False)
    if c1_filtered == c2_filtered:
        return IntrCompRes(equal=True)

    f1 = git_log1('/tmp/%h-%f.patch', c1)
    with open(f1, 'w') as f:
        f.write(c1_filtered)

    f2_prefix = '' if c2_ind is None else f'[{c2_ind}]'
    f2 = git_log1(f'/tmp/{f2_prefix}%h-%f.patch', c2)
    with open(f2, 'w') as f:
        f.write(c2_filtered)

    if comment is None:
        comment_path = None
        meta_tab_opened = False
    else:
        comment_fd, comment_path = mkstemp()
        with open(comment_fd, 'w') as f:
            f.write(comment)
        meta_tab_opened = comment.strip() != ''

    while True:
        res = run_vim(f1, f2, comment_path, meta_tab_opened)

        ar = apply_patch_changes(c1, c1_branch, c1_orig, c1_filtered, f1)
        if ar.action == TriWay.RETRY:
            continue

        if ar.action == TriWay.STOP:
            res.stop = True
            break

        res.new_c1 = ar.new_hash

        ar = apply_patch_changes(c2, c2_branch, c2_orig, c2_filtered, f2)
        if ar.action == TriWay.RETRY:
            continue

        if ar.action == TriWay.STOP:
            res.stop = True
            break

        res.new_c2 = ar.new_hash

        assert not (res.new_c1 and res.new_c2)

        break

    if comment is not None:
        with open(comment_path) as f:
            res.comment = f.read()
        os.unlink(comment_path)

    return res
