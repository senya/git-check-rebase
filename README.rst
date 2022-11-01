git check-rebase
================

Installation
------------

::

    pip install git-check-rebase

Description
-----------

``git-check-rebase`` is an utility for different kinds of git branch rebasing control. git-check-rebase compares several git commit ranges and produce a comparison table, where columns corresponds to specified ranges (and there are some additional helping columns).

The last range (the rightmost in the command line) produces *the sequence*. All rows of the resulting table correspond to comments from *the sequence* and the column corresponding to the sequence is a kind of ``git log --oneline --reverse``.

For each commit of the sequence ``git-check-rebase`` searches for corresponding commit in other ranges and fills corresponding cells in other range columns.

Then ``git-check-rebase`` compares the commits in the each line and mark equal commits by green color. There is also a possibility to compare commits in `--interactive` mode and mark them as checked. In this case leftmost commit in a row is green and the equal (checked by hand) commit is yellow.

Short example:

.. image:: https://gitlab.com/vsementsov/git-check-rebase/-/raw/ea72a4b7ccaefcad6424b09fa5ae6b69fd1d2e63/docs/_static/img/ex1.png

Here first commit is equal in both ``v1`` and ``v2`` of the ``feature`` branch, second commit is marked ``ok`` during `--interactive` session, third commit is not checked (and not equal) and the last one is absent in ``v1``, so it's "new".

Use cases
---------

When ``git-check-rebase`` can help?

- Check difference between versions of upstream series
- Check backported series
- Check status of rebasing a downstream branch to a new upstream release
- Check upstreaming status of commits in downstream branch

Documentation
-------------

Full documentation is `here <https://git-check-rebase.readthedocs.io/en/upd/>`_
