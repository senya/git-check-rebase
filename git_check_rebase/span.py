try:
    from termcolor import colored
    has_colored = True
except ImportError:
    print('for colors install termcolor python module')
    has_colored = False


def colored_html(s, color):
    if color is None:
        return s
    swap = {'yellow': 'orange', 'cyan': 'DarkCyan'}
    color = swap.get(color, color)
    return '<span style="color: {}">{}</span>'.format(color, s)


def mega_colored(s, color):
    if color is None or not has_colored:
        return s

    return colored(s, color)


class Span:
    def __init__(self, text, fmt='colored', klass=None):
        self.text = text
        self.klass = klass
        self.fmt = fmt

    def __str__(self):
        if self.fmt == 'colored':
            mapping = {
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
            return mega_colored(self.text, mapping[self.klass])
        elif self.fmt == 'html':
            return colored_html(self.text, self.klass)
        else:
            return self.text
