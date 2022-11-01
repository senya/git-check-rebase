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


class Feature:
    def __init__(self, name, group=None):
        assert group is None
        self.feature = name
        self.drop = ''
        self.upstreaming = None

    def add_property(self, prop):
        if prop == 'drop':
            assert not self.drop
            self.drop = 'drop'
        else:
            key, val = [x.strip() for x in prop.split(':', 2)]
            assert val
            if key == 'drop':
                self.drop = 'drop-' + val
            else:
                assert key == 'upstreaming'
                self.upstreaming = val


class DropGroup:
    def __init__(self, name, group=None):
        self.feature = group.feature if group else None
        self.drop = 'drop-' + name if name else 'drop'
        self.upstreaming = None

    def add_property(self, prop):
        raise ValueError


class CommitMeta(Feature):
    def __init__(self, subject, group=None):
        self.subject = subject
        self.comment = ''
        self.checked = []
        self.feature = group.feature if group else None
        self.drop = group.drop if group else None
        self.upstreaming = group.upstreaming if group else None

    def add_comment_line(self, comment):
        if self.comment:
            self.comment += '\n'
        self.comment += comment

    def add_checked_pair(self, h1, h2):
        self.checked.append((h1, h2))

    def add_property(self, prop):
        if prop.startswith('drop') or prop.startswith('upstreaming'):
            super().add_property(prop)
            return

        if prop.startswith('ok:'):
            self.add_checked_pair(*(prop.split()[1:]))
        else:
            self.add_comment_line(prop)


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

        groups_stack = []
        current_obj = None

        with open(fname) as f:
            for line in f:
                line = line.rstrip()

                if not line or line[0] == '#':
                    continue

                if line[0:2] == '  ':
                    current_obj.add_property(line[2:])

                elif line[0] == '=':
                    assert isinstance(current_obj, CommitMeta)
                    self.aliases[subject_to_key(line[1:])] = \
                        subject_to_key(current_obj.subject)

                elif line[-1] == ':':
                    print('"tag:" syntax is deprecated. '
                          'Use "%feature: <tag> <commits> %end" for '
                          'grouping by features, "%drop: <tag> <commits> %end"'
                          ' for drop grouping.')
                    # Addition properties are not allowed for deprecated tag
                    current_obj = None
                    # Mimic old behavior: tag clears previous tag
                    if line.startswith('drop'):
                        reason = line[4:-1]
                        if reason and reason[0] == '-':
                            reason = reason[1:]
                        groups_stack = [DropGroup(reason)]
                    else:
                        groups_stack = [Feature(line[:-1])]

                elif line[0] == '%':
                    if line == '%end':
                        current_obj = None
                        del groups_stack[-1]
                    else:
                        key, val = [x.strip() for x in line.split(':', 2)]
                        if key == '%feature':
                            current_obj = Feature(val)
                        else:
                            assert key == '%drop'
                            current_obj = DropGroup(val)
                        groups_stack.append(current_obj)

                else:
                    # Normal commit
                    if subject_to_key(line) in self.by_key:
                        raise ValueError('Double definition for: ' + line)
                    group = groups_stack[-1] if groups_stack else None
                    current_obj = CommitMeta(line, group=group)
                    self.by_key[subject_to_key(line)] = current_obj

    def alias_to_key(self, alias):
        return self.aliases.get(alias, alias)

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
