import sys
import subprocess


def git(cmd):
    return subprocess.run('git ' + cmd, shell=True, encoding='utf-8',
                          check=True, stdout=subprocess.PIPE).stdout


def git_log1(format, rev):
    cmd = f"log -1 --format='{format}' {rev}"
    try:
        return git(cmd).strip()
    except subprocess.CalledProcessError as e:
        # assume, git will print error message
        sys.exit(e.returncode)


def git_log(format, param):
    cmd = "log --reverse --date=format:'%d.%m.%y %H:%M' " \
        "'--pretty=format:{}' {}".format(format, param)

    try:
        lines = git(cmd).split('\n')
    except subprocess.CalledProcessError as e:
        # assume, git will print error message
        sys.exit(e.returncode)

    return lines


def git_log_table(format, param, splitter='$%^@'):
    lines = git_log(format.replace(' ', splitter), param)

    return (line.split(splitter) for line in lines if line)


def git_get_git_dir():
    return git('rev-parse --git-common-dir').strip()
