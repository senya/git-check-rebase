git check-rebase
================

Installation
------------

Use pip package manager in any way you prefer. For example:

    pip3 install git+https://gitlab.com/vsementsov/git-check-rebase.git


.. program:: git-check-rebase

Synopsis
~~~~~~~~

**git-check-rebase** [options] range [range ...]

Description
~~~~~~~~~~~

``git-check-rebase`` is an utility for different kinds of git branch rebasing control. git-check-rebase compares several git commit ranges and produce a comparison table, where columns corresponds to specified ranges (and there are some additional helping columns).

The last range (the rightmost in the command line) produces *the sequence*. All rows of the resulting table correspond to comments from *the sequence* and the column corresponding to the sequence is a kind of ``git log --oneline --reverse``.

For each commit of the sequence ``git-check-rebase`` searches for corresponding commit in other ranges and fills corresponding cells in other range columns.

Then ``git-check-rebase`` compares the commits in the each line and mark equal commits by :green:`green` color. There is also a possibility to compare commits in :option:`--interactive` mode and mark them as checked. In this case leftmost commit in a row is :green:`green` and the equal (checked by hand) commit is :yellow:`yellow`.

Short example:

    .. image:: docs/_static/img/ex1.png

    Here first commit is equal in both ``v1`` and ``v2`` of the ``feature`` branch, second commit is marked ``ok`` during :option:`--interactive` session, third commit is not checked (and not equal) and the last one is absent in ``v1``, so it's "new".

Documentation
~~~~~~~~~~~~~

Full documentation is `here <https://git-check-rebase.readthedocs.io/en/upd/>`_
