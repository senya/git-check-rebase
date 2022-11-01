from setuptools import setup

setup(name='git-check-rebase',
      version='0.2',
      description='Some useful scripts to operate track history and patch '
                  'changes during rebases.',
      author='Vladimir Sementsov-Ogievskiy',
      author_email='vsementsov@yandex-team.ru',
      license='MIT',
      scripts=['git-check-rebase'],
      url='https://gitlab.com/vsementsov/git-check-rebase',
      install_requires=['tabulate', 'termcolor'])
