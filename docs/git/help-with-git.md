# Dangit, Git!?!

Git is hard: messing up is easy, and figuring out how to fix your mistakes is impossible. Git documentation has this chicken and egg problem where you can't search for how to get yourself out of a mess, _unless you already know the name of the thing you need to know about_ in order to fix your problem.

So here are some bad situations I've gotten myself into, and how I eventually got myself out of them _in plain english_.

## [Dangit, I did something terribly wrong, please tell me git has a magic time machine!?!](https://dangitgit.com/en#magic-time-machine)

```git
git reflog
# you will see a list of every thing you've
# done in git, across all branches!
# each one has an index HEAD@{index}
# find the one before you broke everything
git reset HEAD@{index}
# magic time machine

```

You can use this to get back stuff you accidentally deleted, or just to remove some stuff you tried that broke the repo, or to recover after a bad merge, or just to go back to a time when things actually worked. I use `reflog` A LOT. Mega hat tip to the many many many many many people who suggested adding it!

## [Dangit, I committed and immediately realized I need to make one small change!](https://dangitgit.com/en#change-last-commit)

```git
# make your change
git add . # or add individual files
git commit --amend --no-edit
# now your last commit contains that change!
# WARNING: never amend public commits
```

This usually happens to me if I commit, then run tests/linters... and ugh, I didn't put a space after an equals sign. You could also make the change as a new commit and then do `rebase -i` in order to squash them both together, but this is about a million times faster.

_Warning: You should never amend commits that have been pushed up to a public/shared branch! Only amend commits that only exist in your local copy or you're gonna have a bad time._

## [Dangit, I need to change the message on my last commit!](https://dangitgit.com/en#change-last-commit-message)

```git
git commit --amend 
# follow prompts to change the commit message
```

Stupid commit message formatting requirements.

## [Dangit, I accidentally committed something to master that should have been on a brand new branch!](https://dangitgit.com/en#accidental-commit-master)

```git
# create a new branch from the current state of master
git branch some-new-branch-name
# remove the last commit from the master branch
git reset HEAD~ --hard
git checkout some-new-branch-name
# your commit lives in this branch now :)
```

Note: this doesn't work if you've already pushed the commit to a public/shared branch, and if you tried other things first, you might need to `git reset HEAD@{number-of-commits-back}` instead of `HEAD~`. Infinite sadness. Also, many many many people suggested an awesome way to make this shorter that I didn't know myself. Thank you all!

## [Dangit, I accidentally committed to the wrong branch!](https://dangitgit.com/en#accidental-commit-wrong-branch)

```git
# undo the last commit, but leave the changes available
git reset HEAD~ --soft
git stash
# move to the correct branch
git checkout name-of-the-correct-branch
git stash pop
git add . # or add individual files
git commit -m "your message here"
# now your changes are on the correct branch
```

A lot of people have suggested using `cherry-pick` for this situation too, so take your pick on whatever one makes the most sense to you!

```git
git checkout name-of-the-correct-branch
# grab the last commit to master
git cherry-pick master
# delete it from master
git checkout master
git reset HEAD~ --hard
```

## [Dangit, I tried to run a diff but nothing happened?!](https://dangitgit.com/en#dude-wheres-my-diff)

If you know that you made changes to files, but `diff` is empty, you probably `add`\-ed your files to staging and you need to use a special flag.

```git
git diff --staged
```

File under ¯\\\_(ツ)\_/¯ (yes, I know this is a feature, not a bug, but it's baffling and non-obvious the first time it happens to you!)

## [Dangit, I need to undo a commit from like 5 commits ago!](https://dangitgit.com/en#undo-a-commit)

```git
# find the commit you need to undo
git log
# use the arrow keys to scroll up and down in history
# once you've found your commit, save the hash
git revert [saved hash]
# git will create a new commit that undoes that commit
# follow prompts to edit the commit message
# or just save and commit
```

Turns out you don't have to track down and copy-paste the old file contents into the existing file in order to undo changes! If you committed a bug, you can undo the commit all in one go with `revert`.

You can also revert a single file instead of a full commit! But of course, in true git fashion, it's a completely different set of commands...

## [Dangit, I need to undo my changes to a file!](https://dangitgit.com/en#undo-a-file)

```git
# find a hash for a commit before the file was changed
git log
# use the arrow keys to scroll up and down in history
# once you've found your commit, save the hash
git checkout [saved hash] -- path/to/file
# the old version of the file will be in your index
git commit -m "Wow, you don't have to copy-paste to undo"
```

When I finally figured this out it was HUGE. HUGE. H-U-G-E. But seriously though, on what planet does `checkout --` make sense as the best way to undo a file? :shakes-fist-at-linus-torvalds:

## [Forget this noise, I give up.](https://dangitgit.com/en#forget-this-noise)

```git
cd ..
sudo rm -r stupid-git-repo-dir
git clone https://some.github.url/stupid-git-repo-dir.git
cd stupid-git-repo-dir
```

Thanks to Eric V. for this one. All complaints about the use of `sudo` in this joke can be directed to him.

For real though, if your branch is sooo borked that you need to reset the state of your repo to be the same as the remote repo in a "git-approved" way, try this, but beware these are destructive and unrecoverable actions!

```git
# get the lastest state of origin
git fetch origin
git checkout master
git reset --hard origin/master
# delete untracked files and directories
git clean -d --force
# repeat checkout/reset/clean for each borked branch
```

\*Disclaimer: This site is not intended to be an exhaustive reference. And yes, there are other ways to do these same things with more theoretical purity or whatever, but I've come to these steps through trial and error and lots of swearing and table flipping, and I had this crazy idea to share them with a healthy dose of levity. Take it or leave it as you will!

## Reference

- https://dangitgit.com/en
