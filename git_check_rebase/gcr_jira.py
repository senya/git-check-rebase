from typing import Iterable, Any
from getpass import getpass

import jira  # type: ignore
from jira.utils import json_loads  # type: ignore


class GCRIssue:
    def __init__(self, tracker: 'GCRTracer', issue: Any) -> None:
        self.tracker = tracker
        self._issue = issue

    @property
    def key(self):
        return self._issue.key

    @property
    def description(self):
        return self._issue.fields.description

    def is_critical(self) -> bool:
        return self._issue.fields.priority.name in ('Critical', 'Blocker')

    def is_fixed(self) -> bool:
        resol = self._issue.fields.resolution
        return resol and resol.name == 'Fixed'

    def get_subissues(self) -> Iterable['GCRIssue']:
        if self._issue.fields.issuetype.name == 'Epic':
            path = f'/rest/agile/1.0/epic/{self.key}/issue'
            issues = self.tracker.get_json(path)['issues']
            return (self.tracker.get_issue(iss['key']) for iss in issues)

        return (GCRIssue(self.tracker, sub)
                for sub in self._issue.fields.subtasks)


class GCRTracer:
    def __init__(self) -> None:
        server = input('Jira server: ')
        if not server.startswith('http'):
            server = 'https://' + server
        login = input('Login: ')
        password = getpass()
        self._jira = jira.JIRA(options={'server': server},
                               basic_auth=(login, password))

    def get_json(self, path: str) -> Any:
        assert path[0] == '/'
        url = self._jira.server_url + path
        return json_loads(self._jira._session.get(url))

    def get_issue(self, key: str) -> GCRIssue:
        fields = 'description,subtasks,priority,resolution,issuetype'
        return GCRIssue(self, self._jira.issue(key, fields=fields))
