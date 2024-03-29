
# Ansible Exit Codes

This is more difficult to figure out than it should be.

When you run the `ansible` or `ansible-playbook` command, it will return an exit status depending on what occurred during the run. As usual, an exit code of 0 means success. The non-zero exit codes are where things get a little wild.

The ansible command exit codes are not well-documented, and some of the exit codes can have multiple meanings depending on the type of failure and how it occurred.

[This Github issue](https://github.com/ansible/ansible/issues/19720) tracks some of the discussion around what the exit codes mean. A common recommendation I have encountered, is to test your playbooks to determe what exit codes you will get for a given playbook. Alrighty then…

## Down the rabbit hole[Permalink](#down-the-rabbit-hole "Permalink")

[This file](https://github.com/ansible/ansible/blob/devel/lib/ansible/cli/__init__.py) is a good starting point, as it contains some of the most common errors you may encounter.

Some of the exit codes are passed to Ansible from the [Task Queue Manager](https://github.com/ansible/ansible/blob/devel/lib/ansible/executor/task_queue_manager.py), which handles the gruntwork of dispatching tasks to hosts. This is one area where there can be overlap in return codes between the TQM and the parent ansible commands:

```python
RUN_OK = 0
RUN_ERROR = 1
RUN_FAILED_HOSTS = 2
RUN_UNREACHABLE_HOSTS = 4
RUN_FAILED_BREAK_PLAY = 8
RUN_UNKNOWN_ERROR = 255
```

With the above in mind, below is a best-effort at distilling the various exit codes returned by ansible commands using Ansible 2.9:

-   `0` = The command ran successfully, without any task failures or internal errors.
-   `1` = There was a fatal error or exception during execution.
-   `2` = Can mean any of:
    -   Task failures were encountered on some or all hosts during a play (partial failure / partial success).
    -   The user aborted the playbook by hitting `Ctrl+C, A` during a `pause` task with `prompt`.
    -   Invalid or unexpected arguments, i.e. `ansible-playbook --this-arg-doesnt-exist some_playbook.yml`.
    -   A syntax or YAML parsing error was encountered during a _dynamic_ include, i.e. `include_role` or `include_task`.
-   `3` = This used to mean “Hosts unreachable” per TQM, but that seems to have been redefined to `4`. I’m not sure if this means anything different now. (ref1,ref4)
-   `4` = Can mean any of:
    -   Some hosts were unreachable during the run (login errors, host unavailable, etc). _This will NOT end the run early._ (ref4)
    -   All of the hosts within a single batch were unreachable- i.e. if you set `serial: 3` at the play level, and three hosts in a batch were unreachable. _This WILL end the run early._
    -   A synax or parsing error was encountered- either in command arguments, within a playbook, or within a _static_ include (`import_role` or `import_task`). _This is a fatal error._ (ref1)
-   `5` = Error with the options provided to the command (ref3)
-   `6` = Command line args are not UTF-8 encoded (ref1)
-   `8` = A condition called RUN\_FAILED\_BREAK\_PLAY occurred within Task Queue Manager. (ref4)
-   `99` = Ansible received a keyboard interrupt (SIGINT) while running the playbook- i.e. the user hits `Ctrl+c` during the playbook run.
-   `143` = Ansible received a kill signal (SIGKILL) during the playbook run- i.e. an outside process kills the `ansible-playbook` command.
-   `250` = Unexpected exception- often due to a bug in a module, jinja templating errors, etc. (ref1)
-   `255` = Unknown error, per TQM. (ref4)

References:

-   [ref1](https://github.com/ansible/ansible/blob/devel/lib/ansible/cli/__init__.py)
-   [ref2](https://github.com/ansible/ansible/blob/devel/lib/ansible/playbook/__init__.py)
-   [ref3](https://github.com/ansible/ansible/blob/devel/lib/ansible/cli/adhoc.py)
-   [ref4](https://github.com/ansible/ansible/blob/devel/lib/ansible/executor/task_queue_manager.py)

## Summary[Permalink](#summary "Permalink")

The main takeaways for an operator, from the above testing:

-   Exit codes `2` and `4` are overloaded, with different components using them to indicate different things. Depending on your playbook and expected behavior, they _may_ indicate a “partial success” status due to host availability or isolated task failures.
-   You also cannot reliably determine whether a playbook ended early, based on a `2` or `4` exit code- it depends on which failures were encountered. You will need other means within or outside of the playbook, to determine without a doubt if all tasks were executed. Tools like AWX/Tower, ARA, or Rundeck could provide some visibility into this.
-   Syntax errors encountered within a _static_ include (`import_X`), are likely to kill the run early with an exit status of `4` (generic YAML parser error). Static includes are compiled at the beginning of the run, making syntax errors more likely to be caught early.
-   Syntax errors encountered within a _dynamic_ include (`include_X`), are likely to result in an exit status of `2`, and NOT end the run early. They will be treated instead as a task failure for whatever task included the buggy code.

## Reference

- https://jwkenney.github.io/ansible-return-codes/
- https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_error_handling.html
- 
