import re
import os
import subprocess

from simple_git import git, git_get_git_dir, git_log1

eat_numbers_subs = [
    [r'^index .*', 'index <some index>'],
    [r'^commit .*', 'commit <some commit>'],
    [r'^Date:.*00', 'Date: <some date>'],
    [r'^@@ .* @@', '@@ <some lines> @@'],
]
for e in eat_numbers_subs:
    e[0] = re.compile(e[0], re.MULTILINE)

empty_line_changes_subs = [
    [r'^\+\n', ''],
    [r'^\-\n', ''],
]
for e in empty_line_changes_subs:
    e[0] = re.compile(e[0], re.MULTILINE)

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


def vimdiff_commits(c1, c2, c2_ind=None):
    c1_text = eat_numbers(git('show ' + c1), ignore_empty_lines=False)
    c2_text = eat_numbers(git('show ' + c2), ignore_empty_lines=False)
    if c1_text == c2_text:
        return

    f1 = git_log1('/tmp/%h-%f.patch', c1)
    with open(f1, 'w') as f:
        f.write(c1_text)

    f2_prefix = '' if c2_ind is None else f'[{c2_ind}]'
    f2 = git_log1(f'/tmp/{f2_prefix}%h-%f.patch', c2)
    with open(f2, 'w') as f:
        f.write(c2_text)

    return subprocess.run(['vimdiff', f1, f2])
