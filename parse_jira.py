import jira


def parse_issue(j, key, commits, result):
    issue = j.issue(key, fields='description,subtasks,priority,resolution')

    if issue.fields.description:
        for line in issue.fields.description.split('\n'):
            line = line.strip()
            for commit in commits:
                if line.endswith(commit):
                    if commit in result:
                        result[commit][key] = issue
                    else:
                        result[commit] = {key: issue}

    for sub in issue.fields.subtasks:
        parse_issue(j, sub.key, commits, result)


def parse_jira(server, login, password, issues, commits):
    """ Recursively search issues for commits mentioned in description

    Search issues (and their subtasks) for description lines, ends with commit
    subjects from commits list

    Returns dict {commit => [list of matching issues]}
    """
    j = jira.JIRA(options={'server': server}, basic_auth=(login, password))

    result = {}

    for issue in issues:
        parse_issue(j, issue, commits, result)

    return {k: v.values() for k, v in result.items()}
