
# Ansible: Default Variables Values

In Ansible it is recommended to set default values for variables to avoid undefined-variable errors:

> The task includes an option with an undefined variable.

The default variables for a role can be defined in the `defaults/main.yml` file that might look something like this:

```
nginx_version: 1.20.1
nginx_service_name: "nginx.service"
```

Ansible will use the default values only if those variables are not defined anywhere else.

**Cool Tip:** Ansible Playbook – Print Variable & List All Variables! [Read more →](https://www.shellhacks.com/ansible-debug-print-variable-list-all-variables-playbook/)

Another option is to set the default values for the variables using the Jinja’s `default` filter:

```
"{{ some_variable | default('default_value') }}"
```

This is often a better approach than failing if a variable is not defined.

Passing in a `true` as the second parameter will return the default value if the value is defined but blank:

```
"{{ some_variable | default('default_value', true) }}"
```

## Reference

- https://www.shellhacks.com/ansible-default-variables-values/
