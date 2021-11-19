import sys
import subprocess


def git(cmd, **args):
    return subprocess.run('git ' + cmd, shell=True, encoding='utf-8',
                          check=True, stdout=subprocess.PIPE,
                          **args).stdout


def git_log1(fmt, rev):
    cmd = f"log -1 --format='{fmt}' {rev}"
    try:
        return git(cmd).strip()
    except subprocess.CalledProcessError:
        # assume, git will print error message
        sys.exit(f'git {cmd} failed')


def git_log(fmt, param):
    cmd = "log --reverse --date=format:'%d.%m.%y %H:%M' " \
        "'--pretty=format:{}' {}".format(fmt, param)

    try:
        lines = git(cmd).split('\n')
    except subprocess.CalledProcessError:
        # assume, git will print error message
        sys.exit(f'git {cmd} failed')

    return lines


def git_log_table(fmt, param, splitter='$%^@'):
    lines = git_log(fmt.replace(' ', splitter), param)

    return (line.split(splitter) for line in lines if line)


def git_get_git_dir():
    return git('rev-parse --git-common-dir').strip()
