import sys

def colored_stub(s, *args, **vargs):
    return s


def colored_html(s, color):
    if color is None:
        return s
    swap = {'yellow': 'orange', 'cyan': 'DarkCyan'}
    color = swap.get(color, color)
    return '<span style="color: {}">{}</span>'.format(color, s)


colored_console = colored_stub
if sys.stdout.isatty():
    try:
        import termcolor
        colored_console = termcolor.colored
    except ImportError:
        print('for colors install termcolor module')


def mega_colored(s, color):
    if color is None:
        return s

    return colored_console(s, color)


class Span:
    def __init__(self, text, format='colored', klass=None):
        self.text = text
        self.klass = klass
        self.format = format

    def __str__(self):
        if self.format == 'colored':
            mapping = {
                'bug-critical': 'red',
                'bug-fixed': 'green',
                'bug': 'cyan',
                'unknown': 'red',
                'matching': 'green',
                'checked': 'yellow',
                'drop': 'magenta',
                None: None
            }
            return mega_colored(self.text, mapping[self.klass])
        elif self.format == 'html':
            return colored_html(self.text, self.klass)
