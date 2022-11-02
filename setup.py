from setuptools import setup
from pathlib import Path

setup(name='git-check-rebase',
      version='0.3',
      description='Some useful scripts to operate track history and patch '
                  'changes during rebases.',
      author='Vladimir Sementsov-Ogievskiy',
      author_email='vsementsov@yandex-team.ru',
      long_description=Path('README.rst').read_text(),
      long_description_content_type='text/x-rst',
      license_files = ('LICENSE'),
      license='MIT',
      scripts=['git-check-rebase'],
      packages=['git_check_rebase'],
      url='https://gitlab.com/vsementsov/git-check-rebase',
      install_requires=['tabulate', 'termcolor'])
