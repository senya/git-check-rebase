from .compare_ranges import GitHashCell, Table, RowsHideLevel
import tabulate
from .viewable import Viewer, Span, GitHashCell

tabulate.PRESERVE_WHITESPACE = True

colors = {
    'bug-critical': 'red',
    'bug-fixed': 'green',
    'matching': 'green',
    'bug': 'cyan',
    'unknown': 'red',
    'equal': 'green',
    'base': 'green',
    'checked': 'yellow',
    'drop': 'magenta',
    'none': None,
    None: None
}

class TextViewer(Viewer):
    list_splitter = '\n'

    def __init__(self, color: bool = False) -> None:
        if color:
            from termcolor import colored
            self.styled = lambda text, style: colored(text, colors[style])
        else:
            self.styled = lambda text, style: text

    def view_git_hash(self, h: GitHashCell) -> str:
        return self.styled(h.commit_hash, h.comp.name.lower())

    def view_span(self, s: Span) -> str:
        return self.styled(s.text, s.klass)

    def view_converted_table(self, tab) -> str:
        return tabulate.tabulate(tab, tablefmt='plain')
