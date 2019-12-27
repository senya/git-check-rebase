from flask import Flask
import subprocess

app = Flask(__name__)

@app.route('/')
def main():
    return subprocess.run('cd /work/src/qemu/vz-8.1; /work/proj/git-range-diff/git-range-diff --meta /work/proj/git-range-diff/porting-to-8.1-new vz-8.1:vz-8.1-base..vz-8.1 v4.1.0 rh-8.1:v4.1.0..vz-8.1-base master-top:v4.1.0..master vz-8.0:our/vz-8.0-base..our/vz-8.0 --jira PSBM-100595 --html', shell=True, stdout=subprocess.PIPE).stdout

