import sys

from parse_jira import parse_jira
from simple_git import git_log_table
from compare_commits import are_commits_equal
from meta import Meta, subject_to_key
from span import Span


class CommitRange:
    def __init__(self, definition, meta=None):
        if ':' in definition:
            self.name, self.git_range = definition.split(':', 1)
        else:
            self.name = definition
            self.git_range = definition

        lines = git_log_table('%h %s', self.git_range)

        self.by_key = {}
        for l in lines:
            try:
                h, s = l
            except:
                print(l)
                exit(0)
            key = subject_to_key(s, meta)

            self.by_key[key] = h


def git_range_diff_table(ranges, meta=None, jira=None, jira_issues=None,
                         fmt='colored', headers=True, date_column=True,
                         author_column=True, bench_func=lambda x: None):
    """
    ranges: [CommitRange]
    meta: Meta
    jira_issues: [str]
    fmt: 'colored' | 'html'

    Returns list of lists with printable objects
    """
    seq = ranges[-1]

    log = git_log_table('%h %ad %an %s', seq.git_range)

    bench_func('before git_range_diff_table')

    if jira_issues:
        log1 = git_log_table('%h %ad %an %s', seq.git_range)
        auth, server = jira.rsplit('@', 1)
        user, password = auth.split(':', 1)
        jira = parse_jira('https://' + server, user, password, jira_issues,
                          [line[-1] for line in log1])
        jira = {subject_to_key(k): v for k, v in jira.items()}
        bench_func('jira')


    if headers:
        out = [['<tag>']] if meta else [[]]
        out[0] += [r.name for r in ranges]
        if date_column:
            out[0].append('DATE')
        if author_column:
            out[0].append('AUTHOR')
        out[0].append('SUBJECT')
    else:
        out = []
    for commit in log:
        ad = commit[1]
        an = commit[2]
        if an == 'Vladimir Sementsov-Ogievskiy':  # too long :)
            an = "Vladimir S-O"
        s = commit[3]
        key = subject_to_key(s, meta)
        line = [Span(r.by_key.get(key, ''), fmt) for r in ranges]
        if date_column:
            line.append(ad)
        if author_column:
            line.append(an)
        line.append(s)
        if meta:
            text = meta.get_tag(key) or ''
            klass = 'drop' if text.startswith('drop') else None
            line.insert(0, Span(text, fmt, klass))

        ind = 1 if meta else 0
        comp_ind = ind
        if line[ind].text == '':
            comp_ind = ind + len(ranges) - 1

        bench_func('before compare loop')
        found = False
        for i in range(ind + 1, ind + len(ranges)):
            if i == comp_ind:
                break
            if line[i].text != '':
                if are_commits_equal(line[comp_ind].text, line[i].text):
                    found = True
                    line[i].klass = 'matching'
                elif meta and key in meta.by_key and meta.by_key[key].checked:
                    for a, b in meta.by_key[key].checked:
                        if (are_commits_equal(a, line[i].text) and
                                are_commits_equal(b, line[comp_ind].text)) or \
                            (are_commits_equal(b, line[i].text) and
                                are_commits_equal(a, line[comp_ind].text)):
                            found = True
                            line[i].klass = 'checked'
                            break
        if found:
            line[comp_ind].klass = 'matching'
        bench_func('compare loop')

        if jira and key in jira:
            issues = jira[key]
            crit = any(issue.fields.priority.name in ('Critical', 'Blocker')
                       for issue in issues)
            fixed = all(issue.fields.resolution and
                        issue.fields.resolution.name == 'Fixed'
                        for issue in issues)
            text = ','.join(issue.key for issue in issues)

            if line[0].text:
                line[0].text += '(' + text + ')'
            else:
                line[0].text = text

            if fixed:
                line[0].klass = 'bug-fixed'
            elif crit:
                line[0].klass = 'bug-critical'
            else:
                line[0].klass = 'bug'
            bench_func('jira handling')

        if meta and not any(cell.text for cell in line[:ind + len(ranges) - 1]):
            line[0].text = '???'
            line[0].klass = 'unknown'
            bench_func('??? handling')

        out.append([line[i] for i in range(len(line))])

        if meta and key in meta.by_key and meta.by_key[key].comment:
            out.append([''] * len(out[-1]))
            out[-1][-1] = meta.by_key[key].comment

    return out
