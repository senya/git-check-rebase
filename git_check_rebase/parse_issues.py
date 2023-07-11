from typing import Any, List, Dict, Set


def parse_issue(issue: Any, commits: List[str],
                result: Dict[str, List[Any]],
                parsed_keys: Set[str]) -> None:
    """Update @result: dict {commit => [list of matching issues]}"""
    if issue.key in parsed_keys:
        return
    parsed_keys.add(issue.key)

    if issue.description:
        for line in issue.description.split('\n'):
            line = line.strip()
            for commit in commits:
                if line.endswith(commit):
                    if commit in result:
                        result[commit].append(issue)
                    else:
                        result[commit] = [issue]

    for sub in issue.get_subissues():
        parse_issue(sub, commits, result, parsed_keys)


def parse_issues(tracker: Any, issues: List[str],
                 commits: List[str]) -> Dict[str, List[Any]]:
    """Recursively search issues for commits mentioned in description

    Search issues (and their subtasks) for description lines, ends with commit
    subjects from commits list

    Returns dict {commit => [list of matching issues]}
    """
    result: Dict[str, List[str]] = {}
    parsed_keys: Set[str] = set()

    for issue in issues:
        parse_issue(tracker.get_issue(issue), commits, result, parsed_keys)

    return result
