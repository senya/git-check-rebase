import re
import os
import subprocess
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List
from tempfile import mkstemp

from simple_git import git, git_get_git_dir, git_log1, git_log

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


def sorted_pair(a, b):
    return (a, b) if a <= b else (b, a)


class EqualityCache:
    def __init__(self, fname):
        self._dict = {}
        self.fname = fname

        try:
            with open(fname) as f:
                for line in f:
                    h1, h2, result = line.strip().split(' ', 2)
                    assert result in ('equal', 'differs')

                    self._dict[sorted_pair(h1, h2)] = result == 'equal'
        except FileNotFoundError:
            pass

    def get(self, h1, h2):
        return self._dict.get(sorted_pair(h1, h2))

    def add(self, h1, h2, equal):
        pair = sorted_pair(h1, h2)
        self._dict[pair] = equal

        with open(self.fname, 'a') as f:
            f.write('{} {} {}\n'.format(pair[0], pair[1],
                                        'equal' if equal else 'differs'))


CACHE = EqualityCache(os.path.join(git_get_git_dir(), 'commit-equality-cache'))


def are_commits_equal(c1, c2):
    if c1 == c2:
        return True

    cached = CACHE.get(c1, c2)
    if cached is not None:
        return cached

    c1_text = eat_numbers(git('show --format= ' + c1))
    c2_text = eat_numbers(git('show --format= ' + c2))
    result = c1_text == c2_text

    CACHE.add(c1, c2, result)

    return result


@dataclass
class CompareResults:
    """Type of vimdiff_commits result
    @equal: commits are equal, nothing to compare. Interactive vim was not
            started.
    @ok: user marked the commit pair as OK
    @stop: user requested stop of interactive processing
    @comment: an updated comment
    """
    equal: bool = False
    ok: bool = False
    stop: bool = False
    comment: str = ''


def run_vim(f1: str, f2: str, comment_path: Optional[str],
            meta_tab_opened: bool) -> CompareResults:
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

    Returns CompareResults, where only @ok and @stop may be set, @equal is
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
                '-c', 'cnoreabbrev meta GCheckRebaseToggleMeta',
                '-c', 'command GCheckRebaseOk wa! | cq 200',
                '-c', 'cnoreabbrev ok GCheckRebaseOk']
        if meta_tab_opened:
            cmd += ['-c', ':GCheckRebaseToggleMeta']

    cmd += ['-c', ':norm gg']

    code = subprocess.run(cmd, check=False).returncode
    return CompareResults(ok = code == 200, stop = code not in (0, 200))


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

    status = git('status -uno --porcelain=v1 -b').strip()
    if status != f'## {branch}':
        return ''

    return branch


class TriWay(Enum):
    SKIP = 1
    STOP = 2
    RETRY = 3


def tri_way(problem: str, retry: bool = True, stop_help='') -> TriWay:
    print(f"""You have modified a patch, but we can not update it: {problem}
You have {'three' if retry else 'two'} choices:
1. skip: don't apply the changes, continue interactive process
2. stop: stop the interactive process now. {stop_help}
{'3. retry: review same commit again and fix your changes' if retry else ''}
What to do? [1,2,3]: """)
    ans = input()
    while ans not in ('1', '2', '3'):
        print("you should enter one number, 1 or 2 or 3: ")
        ans = input()

    return TriWay(int(ans))


def apply_patch_changes(commit_hash: str, orig_patch: str, orig_filtered: str,
                        updated_filtered_fname: str) -> TriWay:
    with open(updated_filtered_fname) as f:
        updated_filtered = f.read()

    if updated_filtered == orig_filtered:
        return TriWay.SKIP

    branch = check_git_clean_branch()
    if not branch:
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

    return TriWay.SKIP


def compare_commits(c1, c2, c2_ind=None, comment=None):
    """
    @comment: if None, do simple comparison of two commits and nothing more.
              if str (may be empty), create also temporary file for the
              comment, so that user can modify the comment.
    """
    c1_orig = git('format-patch --stdout -1 ' + c1)
    c1_filtered = eat_numbers(c1_orig, ignore_empty_lines=False)
    c2_orig = git('format-patch --stdout -1 ' + c2)
    c2_filtered = eat_numbers(c2_orig, ignore_empty_lines=False)
    if c1_filtered == c2_filtered:
        return CompareResults(equal=True)

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

        w = apply_patch_changes(c1, c1_orig, c1_filtered, f1)
        if w == TriWay.RETRY:
            continue
        elif w == TriWay.STOP:
            res.stop = True
            break

        w = apply_patch_changes(c2, c2_orig, c2_filtered, f2)
        if w == TriWay.RETRY:
            continue
        elif w == TriWay.STOP:
            res.stop = True
            break

        break

    if comment is not None:
        with open(comment_path) as f:
            res.comment = f.read()
        os.unlink(comment_path)

    return res
