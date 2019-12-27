import re

drop_jira_issue_regex = re.compile(r'(\s*#[A-Z]{3,5}-\d{3,6})+$')


def subject_to_key(subject, meta=None):
    key = subject.strip()
    key = drop_jira_issue_regex.sub('', subject)

    if meta is None:
        return key

    return meta.alias_to_key(key)


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


class Meta:
    def __init__(self, fname):
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
                        commit.add_comment(line)
                        continue

                if line[0] == '=':
                    assert commit is not None
                    self.aliases[subject_to_key(line[1:])] = \
                        subject_to_key(commit.subject)
                    continue

                if line[-1] == ':':
                    tag = line[:-1]
                    continue

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
