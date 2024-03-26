
# Jinja2 Namespaces and Variable Scope

I have been doing some Network automation lately, specifically using the Juniper vSRX and generating config templates via Ansible.

I quickly found out about variable scope in Jinja.

Putting a lot of logic into templates is probably not a good idea, but I’m doing it anyway in this case. :)

Example. I have two friends. One has a car, one doesn’t. Does the group of friends have a car?

```python
#!/usr/bin/env python

from jinja2 import Template

friends = []

friend1 = {
    "name": "Frank",
    "car": False
}
friend2 = {
    "name": "Anna",
    "car": True
}

friends.append(friend1)
friends.append(friend2)

t_example = """
{% set ns = namespace(hasCar=false) %}
{% for f in friends %}
Friend {{ f.name }}
{% if f.car == true %}
{% set ns.hasCar = true %}
{% endif %}
{% endfor %} {# for n in friends #}

{% if ns.hasCar == true %}
SOMEONE HAS A CAR: TRUE
{% else %}
SOMEONE HAS A CAR: FALSE
{% endif %}

"""

template = Template(t_example, trim_blocks=True)

render = template.render(friends=friends)

print render
```

If I run this in ipython I get:

```shell

In [1]: run jinja-ns.py

Friend Frank
Friend Anna

SOMEONE HAS A CAR: TRUE


In [2]:
```

That’s it. Namespaces in jinja.

## Reference

- https://serverascode.com/2018/03/15/jinja2-namespaces.html
- https://j2live.ttl255.com/
- [Version 3 Jinja Spec](https://jinja.palletsprojects.com/en/3.0.x/templates/)
- [Version 2 Jinja Spec](https://jinja.palletsprojects.com/en/2.10.x/templates/)
