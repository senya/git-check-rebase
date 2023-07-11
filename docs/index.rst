.. role:: green
.. role:: yellow

git check-rebase
================

Installation
------------

Use pip package manager in any way you prefer. For example:

    pip install git-check-rebase


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

    .. image:: _static/img/ex1.png

    Here first commit is equal in both ``v1`` and ``v2`` of the ``feature`` branch, second commit is marked ``ok`` during :option:`--interactive` session, third commit is not checked (and not equal) and the last one is absent in ``v1``, so it's "new".

Options
~~~~~~~

.. option:: --meta META

   Use file with metadata for this rebase. Metadata includes information of previously checked commits (marked yellow in the table), information about removed commits (why they are removed). For syntax of meta file see :ref:`Meta syntax` below.

.. option:: --issue-tracker ISSUE_TRACKER

   Specify issue tracker. You may use ``--issue-tracker jira`` for internal jira tracker, or specify any python class available in your system, like ``--issue-tracer my_package.MyTracker``. The class must implement same interface as ``git_check_rebase.gcr_jira.GCRTracer`` (see https://gitlab.com/vsementsov/git-check-rebase/-/blob/master/git_check_rebase/gcr_jira.py).

.. option:: --porting-issues ISSUE_KEY1[,ISSUE_KEY2...]

   Comma separated list of issues, where to search for commits from the *sequence*. Subtasks/subepics are searched too. Issues with description containing some commit subject from the *sequence* are listed in "new" column.

.. option:: --legend

   Show legend above the table - the description of columns and colors.

.. option:: --columns name[,name...]

    You may use a comma-separated combination of following column names:

    index
        row number
    commits
        column group, corresponding to specified ranges

    The following group of columns contains information about the commit in the right-most range:

    feature 
        name of the feature the commit belong to
    cherry
        set, if commit message contains "cherry picked" wording
    date
        author date of the commit
    author
        author of the commit
    msg_issues
        issues, mentioned in the commit message
    subject
        commit subject

    Shortcuts:

    short
        The default. The same as ``commits,subject``.
    full
        The same as ``feature,commits,data,author,subject``.
    all
        All available columns (can't be combined with other column names).

.. option:: --rows-hide-level {show_all,hide_equal,hide_checked}

    How much rows to show:

    show_all
        the default, show all rows

    hide_equal
        hide rows where commits are equal (green)

    hide_checked
        hide rows where commits are equal (green) or checked (yellow)

.. option:: --interactive

   For not-equal commits start an interactive comparison. For each pair of matching but not equeal commits **vim** is called with two patches opened to compare. In vim you may:

   1. Use ``:meta`` command to toggle comment window, where you can put any comment about rebasing that commit. When ``:meta`` command closes the window its contents is saved. You also may save it by normal :w command.

   2. Just exit (``:qa``), to continue the process

   3. Use ``:ok`` command (save all and exit with error status 200) to mark current pair of commits as "OK" and continue the process

   4. Use ``:cq`` (exit with error status 1) to stop the interactive process (all previous results are saved, don't forget to save meta buffer if you need)

   The information (comments and ``ok:`` statuses) is stored into meta file. If ``--meta`` option is not specified, new meta file is created.

   ``--interactive`` may be used only when exatly two ranges are specified.

.. option:: --color, --no-color

   Highlight or not the results. When ``--html`` option is in use ``--no-color`` doesn't make sense: html is always highlighted.
   If unspecified results are highlighted by default if stdout is tty.

.. option:: range

    Range define a set of commits for one column. Range is defined as

    .. code-block::

        [name:]ONERANGE[,ONERANGE...]

    Where ``name`` (if specified) will be used as corresponding column header. ``ONERANGE`` should match one of the following syntax variants:

    <commit>
        It may be any git commit reference, like ``some-tag``, or ``some-branch^^``, or ``some-hash~5``. Declares one commit, i.e. git range ``<commit>~..<commit>``
    <commit1>..<commit2>
        Simple git range, declares ``<commit1>..<commit2>``
    <commit1>..
        Simple git range, declares ``<commit1>..HEAD``
    ..<commit>
        Can be used for any but right-most column. Means ``<default_base>..<commit>`` git range where ``<default_base>`` is base of right-most range. For this to work last range can't be a "multi range", i.e. it shoud not contain a comma ','.
    <ref>~5-
        Defines git range ``<ref>~5..<ref>``. You may use any git reference, like tag or branch name or commit hash and ny combination of ``~`` and ``^`` operators.
    
    **Special range names**

    You can use any names for your commit columns, but some names has special meaning:

    up
        Used for upstream branch. If commit absent in the cell of ``up`` column, it will be filled with ``upstreaming`` or ``drop`` information, found for corresponding commit in meta file or in commit message.

    new
        Used for target branch of rebasing a downstream branch to a new upstream release. If commit absent in the cell of ``new`` column, it will be filled with ``drop`` information, found for corresponding commit in meta file, or with issue key found in the issue tracker (if ``--issue-tracker`` and ``--porting-issues`` are specified)

Meta syntax
~~~~~~~~~~~

Meta file contain meta information about commits of right-most column. Commits are indexed by their subject. So, most of lines of meta file are commit subjects. And there are special syntax defined below to attach some meta information to these subjects.

Comments and empty lines
........................

Empty lines and lines started with ``#`` are ignored.


Tags
....
.. deprecated:: 0.2

This syntax is deprecated

Line ending with ``:`` is a tag. All further commits are marked with this tag, until next tag line. Tag started with ``drop`` marks further commits as dropped.

Features
........

Ideally, commits should contain ``Feature: <...>`` tag in their commit messages. ``git-check-rebase`` parse it and put into ``feature`` column. Still, for old commits that lack this information, features may be defined in meta file, like this:

.. code-block::

    %feature: some-name
    <commit subject>
    <commit subject>
    ...
    %end

Drop groups
...........

When we rebase patches, especially when rebase big downstream project onto new upstream release, we may decide that some patches are to be dropped. And ``git-check-rebase`` can show this information in a resulting table. To define a group of commits to be dropped, use the following syntax:

.. code-block::

    %drop: short-description
    <commit subject>
    <commit subject>
    ...
    %end

``short-description`` may be omitted if not needed. It is also allowed to define drop-group inside of feature-group.


Renamed commits
...............

``git-check-rebase`` searches matching commits by subject, so it can not find renamed commits. To resolve this, you may define equal subjects after commits subject with the following syntax:

.. code-block:: text

    <commit subject>
    =<another commit subject>
    =<and one more commit subject>

Still note: it's a bad practice to rename a commit. Better never do it: you are creating extra work for yourself. As well, never create different commits with equal subjects. Let's subjects be unique.

Checked commits
...............

To mark two hashes as ``checked`` (yellow) in the resulting table:

.. code-block::

   <commit subject>
     ok: <git_hash_1> <git_hash_2>

``git-check-rebase`` can automatically add ``ok:`` tags during ``--interactive`` session.

Other tags
..........

Some special tags may be applied to individual commits or to feature-groups, like this:

.. code-block::

    <some commit>
      tag: value
      another-tag: another-value

    %feature
      tag: value
      tag-without-value

    <commit1>
    <commit2>
    %end

The tags:

``drop``
    Means that commit (or the whole feature) is to be dropped. Equal to placing the commit into ``drop-group``.

``drop: short-description``
    Means that commit (or the whole feature) is to be dropped and adds a short description why. Equal to placing the commit into ``drop-group`` with short description.

``upstreaming: short-description``
    Gives an information on what about to upstream this commit. It may be something like "not-needed" or issue tracker key of corresponding task. This info is shown in smart ``up`` column, when corresponding upstream commit is not found. Similarly with feature, you may specify this bit of meta information in the commit message by ``Upstreaming: <...>`` tag.

Usage examples
~~~~~~~~~~~~~~

The section contains common scenarios where ``git-check-rebase`` is useful.

Compare two commits
...................

For simply compare changes of two commits, for example an original commit and its version rebased to another branch, one can compare outputs of ``git show`` on these commits. But such comparison would have a lot of extra noise: different hashes, a different line numbers. ``git-check-rebase`` compares commits ignoring this noise, so the following command helps:

.. code-block::

    git check-rebase --interactive commit1 commit2

Check new series version for mailing list
.........................................

Assume you have **feature-v2** and **feature-v3** tags. You are going to send **feature-v3** to the mailing list, but want to check what was changed, are all comments on v2 satisfied and fill cover-letter with change description. In this case you simply run:

.. code-block::

   git check-rebase --interactive ..feature-v2 master..feature-v3

Thus you'll see which commits are new, and for changed commits you'll check what was changed.

Check a backport
................

Assume we have ported 10 commits from **master** branch to our **downstream** branch. Let's check, what was changed:

.. code-block::

   git check-rebase --interactive ..master downstream~10-

Rebase of downstream project to a new upstream release
......................................................

OK, that's much more complicated :) Assume we have 300+ patches of downstream based on **upstream-v1**. Downstream patches are written by different people in the team or backported form upstream. Downstream patches belong to different features. Some patches are already included to the new release of upstream. Some patches are to be removed. How to control this process?

The work is long, so to save intermediate results we'll need a meta file. So, create an empty file somewhere. The best thing is to store it in some git repo.

Assume, the original range of commits to forward-port is **upstream-v1..downstream-v1**, and our current state of porting is **upstream-v2..downstream**, where **downstream** is our downstream branch.

Then, iteration of work looks like this:

1. Assume some rebasing work done: you've ported some commits, or make some fixes.

2. Let's check, what we have:

    .. code-block::

        git check-rebase --columns=full --meta /path/to/meta new:upstream-v2..downstream base:..upstream-v2 old:upstream-v1..downstream-v1

Note the differences with previous examples:

- We use ``--columns=full``, it shows also authors and dates of commits, as well as ``feature`` column which helps to distinguish different commit series.

- We use name for the ranges, to have good column headers. Also name ``new`` specifies smart range: when commit is not found, the drop-group meta information would be shown (if exists).

- The **sequence** (the right-most column) is not our *new* branch but *old*. That's because now we are mostly interested in checking the state of each commit in old branch: is it successfully ported or not.

What will we see:

    - some commits are equal in old in new branches, they are most probably OK.

    - some commits are absent in new branch, but present in base. That's very good.

    - some commits are matching in different branches, but not green. We'll want to check them by hand with help of ``--interactive`` mode.

    - some commits are still not forward-ported or somehow lost.

    - some commits are marked as **dropped**.

3. Run same command with ``--interactive`` option and go through unchecked pairs.

4. Edit meta file by hand and define drop-groups, missing features, renamed commits, etc.

In the following example ``docs: add som documentation``, ``hack to fix bug``, ``simple feature``, ``fix test A``, ``fix test B`` are all commit subjects. ``docs: add som documentation`` ``docs: add some documentation`` in a new branch (don't do so, it's a headache!)

Example:

.. code-block::
    
    docs: add some documentation
    =docs: add some documentation
      ok: 2nnf2g2 2u4hghh

    %drop:

    hack to fix bug
       (the commit is removed, as we don't need it anymore)

    simple feature
       (the commit is removed because it's substituted by great feature in a new base)

    %end

    # Don't care to port test fixes if tests pass
    %drop: test-fixes
    fix test A
    fix test B
    %end

Good, you've done a big porting job, and most of commits in your table (be free to call ``git check-rebase`` every time you've modified meta file, or change the history of new branch) are green or yellow or marked as dropped for some reasonable reason. But there are still several features, which are not very necessary for release and you are going to work with them in context of Jira issues. To show this in the table, create Jira issue of you forward-port, create some subtasks in it (optional), and note commit subjects of some commits from the *sequence* in the description of jira issue. Then add corresponding parameters to your ``git check-rebase`` call:

.. code-block::
    
    git check-rebase --issue-tracker jira --porting-issues JIRA_ISSUE_KEY [other options]

Issues noting commit in description will be shown in ``new`` smart column of output table. The color will help to distinguish, critical, non-critical and closed issues.

**NOTE**: I don't work with Jira now, so Jira-related features are not tested and may be broken.

Check downstream-tail status
............................

Sometimes we need to look through our downstream patches, to check what we have and what we forgot to upstream. ``git-check-rebase`` helps again:

.. code-block::

    git check-rebase --meta .git-check-rebase --columns all up:..master our:v6..our-downstream-branch

You may want to commit meta file into your repository - it will define features and upstreaming info, not mentioned in commit messages. And on the next rebase to new upstream release you can add this information into commit messages and drop the meta file.
