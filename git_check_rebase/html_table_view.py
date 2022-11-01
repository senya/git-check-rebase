from .compare_ranges import GitHashCell, Table, RowsHideLevel
from .viewable import Viewer, Span, GitHashCell


colors = {
    'bug-critical': 'red',
    'bug-fixed': 'green',
    'matching': 'green',
    'bug': 'DarkCyan',
    'unknown': 'red',
    'equal': 'green',
    'base': 'green',
    'checked': 'orange',
    'drop': 'magenta',
    'none': None,
    None: None
}


class HtmlViewer(Viewer):
    def view_git_hash(self, h: GitHashCell) -> str:
        href = 'https://bb.yandex-team.ru/projects/CLOUD/repos/' + \
            'qemu/commits/' + h.commit_hash
        col = colors[h.comp.name.lower()]
        return f'<a href="{href}" style="color: {col}">{h.commit_hash}</a>'

    def view_span(self, s: Span) -> str:
        col = colors[s.klass]
        return f'<span style="color: {col}">{s.text}</span>'

    def view_converted_table(self, tab) -> str:
        return '<table>' + \
            '\n'.join('<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>'
                      for row in tab) + '</table>'
