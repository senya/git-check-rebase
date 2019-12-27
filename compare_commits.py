import re
import os

from simple_git import git, git_get_git_dir

eat_numbers_subs = [
    [r'^index .*', 'index <some index>'],
    [r'^@@ .* @@', '@@ <some lines> @@'],
    [r'^\+\n', ''],
    [r'^\-\n', ''],
]
for e in eat_numbers_subs:
    e[0] = re.compile(e[0], re.MULTILINE)


def eat_numbers(patch):
    for e in eat_numbers_subs:
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