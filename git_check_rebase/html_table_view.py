from .viewable import Viewer, Span, GitHashCell, ConvertedTable


colors = {
    'bug-critical': 'red',
    'bug-fixed': 'green',
    'matching': 'green',
    'bug': 'DarkCyan',
    'unknown': 'red',
    'equal': 'green',
    'base': 'green',
    'checked': 'orange',
    'in-tag': 'orange',
    'drop': 'magenta',
    'none': None,
    None: None
}


class HtmlViewer(Viewer):
    def view_git_hash(self, h: GitHashCell) -> str:
        href = 'https://bb.yandex-team.ru/projects/CLOUD/repos/' + \
            'qemu/commits/' + h.commit_hash
        col = colors[h.comp.name.lower()]
        ret = f'<a href="{href}" style="color: {col}">{h.commit_hash}</a>'
        if h.in_tag:
            ret += self.view_span(Span(f' (in {h.in_tag})', 'in-tag'))
        return ret

    def view_span(self, s: Span) -> str:
        col = colors[s.klass]
        return f'<span style="color: {col}">{s.text}</span>'

    def view_converted_table(self, tab: ConvertedTable) -> str:
        return '<table>' + \
            '\n'.join('<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>'
                      for row in tab) + '</table>'
