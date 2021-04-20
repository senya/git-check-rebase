git check-rebase
================

Installation
------------

Use pip package manager in any way you prefer. For example:

    pip3 install git+https://vsementsov@git.sw.ru/scm/~vsementsov/git-check-rebase.git

Description
-----------

git-check-rebase package provides scripts for different kinds of git branch rebasing control. Let's look through the scenarios, from simple to more complicated.

Compare two commits: git-change-diff
------------------------------------

Compare two commits. Git provides a native thing to compare commits - git-diff. But sometimes we need to compare the *changes* that commits do. Like comparing patches. Simple example: you cherry-picked some commit from one branch to another. After resolving the conflicts you want to check, what did you change in commit. You may format patches for the commits to compare and compare them by vimdiff, but there would be alot of noice: a bit different line numbers, different hashes. So, there is a tool, that compares differences ignoring such things: git-change-diff. Usage is simple:

    git change-diff *<rev1>* *<rev2>*  -  compare changes, contributed by commits *rev1* and *rev2*

Compare git ranges: git-check-rebase
------------------------------------

Synopsis
~~~~~~~~

**git-check-rebase** [-h] [--meta META] [--html] [--jira-issues JIRA_ISSUES] [--jira JIRA] [--legend] [--format FORMAT] [--interactive] range [range ...]

Description
~~~~~~~~~~~

git-check-rebase compares several git commit ranges. The algorithm works as follows:

1. Do ``git log --reverse`` for the last range, it's our *sequence*. And it's the right most commit column in the output table (as well as all columns to the right of it, specifying author, date and subject of the commit)

2. For other ranges, for each commit from the *sequence* search for corresponding commit by subject. Thus, we construct the table.

3. For each line, compare commit from first (non-empty) column with other columns. Equal commits marked by green color, previously checked (see ``--meta``) are marked by yellow color.

Options
~~~~~~~

.. program:: git-check-rebase

.. option:: --meta META

   Use file with metadata for this rebase. metadata includes information of previously checked commits (marked yellow in the table), information about removed commits (why they are removed). For syntax of meta file see ``meta syntax`` below.

.. option:: --jira user:password@server

   Specify jira account to be used ``--jira-issues`` option

.. option:: --jira-issues ISSUE_KEY1[,ISSUE_KEY2...]

   Comma separated list of issues, where to search for commits from the *sequence*. Subtasks are searched too. Issues with description containing some commit subject from the *sequence* are listed in meta-column of the output.

.. option:: --legend

   Show legend above the table - the description of columns and colors.

.. option:: --format FORMAT

   Two format are available for now:

   short: the default. Doesn't show meta, author and date columnts. Doesn't show information from meta file except for checked commits (marked by yellow color). Column headers are not printed too. This is convenient for comparing different versions of a branch with one feature, prepared to be sent upstream.

   full: show all columns and meta information, as well as column headers. This is convenient for large rebases of downstream project branch to new upstream version.

.. option:: --interactive

   For not-equal commits start and interactive comparison. For each pair of matching but not equeal commits ``git-change-diff`` is called. Zero return status is considered as "commits are OK", failure as "commits are not OK". Note, that to exit ``vimdiff`` with error code, you should use command ``:cq``. The information is stored into meta file. If ``--meta`` option is not specified, new meta file is created.
   ``--interactive`` may be used only when exatly two ranges are specified.

Ranges:

*range* is ``[name:][base..]top``, where name (if specified) will be used as corresponding column header. If *base* revision is not specified, the whole history of *top* revision is used as range (like for ``git-log`` command).

Meta syntax
~~~~~~~~~~~

1. Empty lines are ignored.

2. Line starting with ``#`` is a comment - ignored.

3. Line ending with ``:`` is a tag. All further commits are marked with this tag. Tag started with ``drop`` marks further commits as dropped.

4. Commit subject in a line sets current commit. When current commit is set, the following lines describe it:

   1. Line `=<another commit subject>` sets equivalent subject.

   2. Line starting with two spaces is a comment for this commit. It will be shown in the table. It's extremely useful for dropped commits, you can describe why commit is dropped.

   3. Line `  ok: <git_hash_1> <git_hash_2>`, specifies that these commit hashes are checked. They will be marked by yellow color in the table
 
Usage examples
~~~~~~~~~~~~~~

1. Preparing a new version of feature branch for upstream. Assume you have feature-v2 and feature-v3 tags. You are going to send feature-v3 to mailing list, but want to check what was changed, are all comments on v2 satisfied and fill cover-letter with change description. In this case you just run:

   git check-rebase --interactive feature-v2 master..feature-v3

Thus you'll see which commits are new, and for changed commits you'll check what was changed.

2. Backporting some feature from upstream to downstream. Assume we have ported 10 commits from master branch to our *downstream* branch. Let's check, what was changed:

   git check-rebase --interactive master downstream~10..downstream

3. Making a rebase of big downstream branch with a lot of features to new upstream version.

The work is long, so to save intermediate results we'll need a meta file. So, create an empty file somewhere. The best thing is to store it in some git repo.

Assume, we have branch downstream, which we are rebasing from upstream-v1 to upstream-v2. Assume original downstream release is tagged downstream-v1. So, the original range of commits to forward-port is **upstream-v1..downstream-v1**, and our current state is **upstream-v2..downstream**

Then, iteration of work looks like this:

1. Assume some rebasing work done: you've ported some commits, or make some fixes.

2. Let's check, what we have:

   git check-rebase --format=full --meta /path/to/meta new:upstream-v2..downstream master base:upstream-v1..upstream-v2 old:upstream-v1..downstream-v1

Note the differences with previous examples:

- We use ``full`` format, it shows also authors and dates of commits, which helps to distinguish different commit series.

- We use tags for some ranges, to have good column headers.

- The **sequence** is not our *new* branch but *old*. That's because now we are mostly interested in checking the state of each commit in old branch: is it successfully ported or not.

What will we see:

    - some commits are equal in old in new branches, they are most probably OK.

    - some commits are absent in new branch, but present in base. That's very good.

    - some commits are matching in different branches, but not green. We'll want to check them by hand.

    - some commits are still not forward-ported or somehow lost.

Now, we should work with our meta file. For example, compare some not green pairs of commits with help of ``git-change-diff`` and add information to meta file, or start ``--interactive`` session of ``git-check-rebase`` which will add information to meta file automatically.

Describe in meta file commits that are removed in a new version, like this:

    drop:

    <some commit subject>
       (the commit is removed, as we don't need it anymore)

    <another commit subject>
       (the commit is removed because it's substituted by great feature in a new base)

    # Don't care to port test fixes if tests pass
    drop-test-fixes:
    <some test fix commit subject>
    <another test fix commit subject>
    <one more test fix commit subject>

If some commit is renamed in a new version, add information to the meta file as well:

    <some commit subject with a type>
    =<new commit subject with fixed type>

Still note: it's a bad practice to rename a commit. Try to never do it: you are creating extra work for yourself. As well, never create different commits with equal subjects. Let's subjects be unique.

Good, you've done a big porting job, and most of commits in your table (be free to call git check-rebase every time you've modified meta file, or change the history of new branch) are green or yellow or marked as dropped for some reasonable reason. But there several features, which are not very necessary for release and you are going to work with them in context of jira issues. To show this in the table, create jira issue of you forward-port, create some subtasks in it (optional), and note commit subjects of some commits from the *sequence* in the description of jira issue. Then add corresponding parameters to your ``git check-rebase`` call:

    git check-rebase --jira user:password@server --jira-issues JIRA_ISSUE_KEY [other options]

Issues noting commit in description will be noted in meta column of output table. The color will help to distinguish, critical, non-critical and closed issues.
