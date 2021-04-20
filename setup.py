from setuptools import setup

setup(name='git-check-rebase',
      version='0.1',
      description='Some useful scripts to operate track history and patch '
          'changes during rebases.',
      author='Vladimir Sementsov-Ogievskiy',
      author_email='vsementsov@virtuozzo.com',
      license='MIT',
      scripts=['git-check-rebase', 'git-change-difftool', 'git-change-diff'])
