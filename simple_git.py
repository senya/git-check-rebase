import sys
import subprocess


def git(cmd):
    return subprocess.run('git ' + cmd, shell=True, encoding='utf-8',
                          check=True, stdout=subprocess.PIPE).stdout


def git_log1(fmt, rev):
    cmd = f"log -1 --format='{fmt}' {rev}"
    try:
        return git(cmd).strip()
    except subprocess.CalledProcessError as e:
        # assume, git will print error message
        sys.exit(e.returncode)


def git_log(fmt, param):
    cmd = "log --reverse --date=format:'%d.%m.%y %H:%M' " \
        "'--pretty=format:{}' {}".format(fmt, param)

    try:
        lines = git(cmd).split('\n')
    except subprocess.CalledProcessError as e:
        # assume, git will print error message
        sys.exit(e.returncode)

    return lines


def git_log_table_one_range(fmt, param, splitter):
    lines = git_log(fmt.replace(' ', splitter), param)

    return (line.split(splitter) for line in lines if line)


def git_log_table(fmt, param, splitter='$%^@'):
    lines = []

    for p in param.split(','):
        lines += git_log_table_one_range(fmt, p, splitter)

    return lines


def git_get_git_dir():
    return git('rev-parse --git-common-dir').strip()
