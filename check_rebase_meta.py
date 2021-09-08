import re
from typing import Optional, Tuple

drop_jira_issue_regex = re.compile(r'(\s*#[A-Z]{3,5}-\d{3,6})+$')


def subject_to_key(subject, meta=None):
    key = subject.strip()
    key = drop_jira_issue_regex.sub('', subject)

    if meta is None:
        return key

    return meta.alias_to_key(key)


def text_add_indent(text: str, indent: int) -> str:
    assert indent > 0

    ws = ' ' * indent
    spl = '\n' + ws

    if text.endswith('\n'):
        text = text[:-1]
        ending = '\n'
    else:
        ending = ''

    return ws + text.replace('\n', spl) + ending


class CommitMeta:
    def __init__(self, subject, tag=None):
        self.subject = subject
        self.tag = tag
        self.comment = ''
        self.checked = []

    def add_comment(self, comment):
        self.comment += comment

    def add_checked_pair(self, h1, h2):
        self.checked.append((h1, h2))


def meta_file_set_comment(fname: str, subject: str, comment: str,
                          ok_pair: Optional[Tuple[str, str]] = None) -> None:
    """ Set commit comment and add new ok_pair (old ok pairs remains) """

    if comment:
        assert comment.strip()
        comment = text_add_indent(comment, 2)
        if comment[-1] != '\n':
            comment += '\n'

    insert_lines = []
    if comment:
        insert_lines.append(comment)
    if ok_pair:
        insert_lines.append(f'  ok: {ok_pair[0]} {ok_pair[1]}\n')

    lines = []
    cur_subj = None
    with open(fname) as f:
        found = False

        for line in f:
            if cur_subj == subject:
                if line[0:2] == '  ':
                    # Skip old comment
                    continue

            lines.append(line)
            line = line.rstrip()

            if line and line[0] not in '# =' and line[-1] != ':':
                cur_subj = line.rstrip()
                if cur_subj == subject:
                    found = True
                    lines += insert_lines

        if not found and insert_lines:
            lines.append(f'\n{subject}\n')
            lines += insert_lines

    with open(fname, 'w') as f:
        f.write(''.join(lines))


class Meta:
    def __init__(self, fname):
        self.fname = fname
        self.by_key = {}
        self.aliases = {}

        tag = None
        commit = None

        with open(fname) as f:
            for line in f:
                if not line.strip():
                    continue

                line = line.rstrip()

                if line[0] == '#':
                    continue

                if commit is not None:
                    if line[0:6] == '  ok: ':
                        commit.add_checked_pair(*(line.split()[1:]))
                        continue
                    if line[0:2] == '  ':
                        commit.add_comment(line[2:])
                        continue

                if line[0] == '=':
                    assert commit is not None
                    self.aliases[subject_to_key(line[1:])] = \
                        subject_to_key(commit.subject)
                    continue

                if line[-1] == ':':
                    tag = line[:-1]
                    continue

                if subject_to_key(line) in self.by_key:
                    raise ValueError('Double definition for: ' + line)
                commit = CommitMeta(line, tag)
                self.by_key[subject_to_key(line)] = commit

    def alias_to_key(self, alias):
        return self.aliases.get(alias, alias)

    def get_tag(self, key):
        if key in self.by_key:
            return self.by_key[key].tag
        else:
            return None

    def subject_to_key(self, subject):
        return subject_to_key(subject, self)

    def get_comment(self, subject: str) -> str:
        key = self.subject_to_key(subject)
        if key in self.by_key:
            return self.by_key[key].comment
        else:
            return ''

    def update_meta(self, subject: str, comment: str,
                    ok_pair: Optional[Tuple[str, str]] = None) -> None:
        """ Set commit comment and add new ok_pair (old ok pairs remains) """
        key = self.subject_to_key(subject)
        if key in self.by_key:
            commit = self.by_key[key]
        else:
            commit = CommitMeta(subject)
            self.by_key[subject_to_key(subject)] = commit

        if not comment.strip():
            comment = ''

        if comment == commit.comment and ok_pair is None:
            # Nothing to do
            return

        commit.comment = comment
        if ok_pair is not None:
            commit.add_checked_pair(*ok_pair)

        meta_file_set_comment(self.fname, commit.subject, comment, ok_pair)
