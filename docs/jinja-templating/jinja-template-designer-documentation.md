
# Template Designer Documentation

**Warning:** This is the development version. The latest stable version is [Version 3.1.x](https://jinja.palletsprojects.com/en/3.1.x/templates/).

This document describes the syntax and semantics of the template engine and will be most useful as reference to those creating Jinja templates. As the template engine is very flexible, the configuration from the application can be slightly different from the code presented here in terms of delimiters and behavior of undefined values.

## Synopsis

A Jinja template is simply a text file. Jinja can generate any text-based format (HTML, XML, CSV, LaTeX, etc.). A Jinja template doesn’t need to have a specific extension: `.html`, `.xml`, or any other extension is just fine.

A template contains **variables** and/or **expressions**, which get replaced with values when a template is _rendered_; and **tags**, which control the logic of the template. The template syntax is heavily inspired by Django and Python.

Below is a minimal template that illustrates a few basics using the default Jinja configuration. We will cover the details later in this document:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <title>My Webpage</title>
</head>
<body>
    <ul id="navigation">
    {% for item in navigation %}
        <li><a href="{{ item.href }}">{{ item.caption }}</a></li>
    {% endfor %}
    </ul>

    <h1>My Webpage</h1>
    {{ a_variable }}

    {# a comment #}
</body>
</html>
```

The following example shows the default configuration settings. An application developer can change the syntax configuration from `{% foo %}` to `<% foo %>`, or something similar.

There are a few kinds of delimiters. The default Jinja delimiters are configured as follows:

-   `{% ... %}` for [Statements](https://jinja.palletsprojects.com/en/latest/templates/#list-of-control-structures)
    
-   `{{ ... }}` for [Expressions](https://jinja.palletsprojects.com/en/latest/templates/#expressions) to print to the template output
    
-   `{# ... #}` for [Comments](https://jinja.palletsprojects.com/en/latest/templates/#comments) not included in the template output
    

[Line Statements and Comments](https://jinja.palletsprojects.com/en/latest/templates/#line-statements) are also possible, though they don’t have default prefix characters. To use them, set `line_statement_prefix` and `line_comment_prefix` when creating the [`Environment`](https://jinja.palletsprojects.com/en/latest/api/#jinja2.Environment "jinja2.Environment").

### Template File Extension

As stated above, any file can be loaded as a template, regardless of file extension. Adding a `.jinja` extension, like `user.html.jinja` may make it easier for some IDEs or editor plugins, but is not required. Autoescaping, introduced later, can be applied based on file extension, so you’ll need to take the extra suffix into account in that case.

Another good heuristic for identifying templates is that they are in a `templates` folder, regardless of extension. This is a common layout for projects.

## Variables

Template variables are defined by the context dictionary passed to the template.

You can mess around with the variables in templates provided they are passed in by the application. Variables may have attributes or elements on them you can access too. What attributes a variable has depends heavily on the application providing that variable.

You can use a dot (`.`) to access attributes of a variable in addition to the standard Python `__getitem__` “subscript” syntax (`[]`).

The following lines do the same thing:

```jinja
{{ foo.bar }}
{{ foo['bar'] }}
```

It’s important to know that the outer double-curly braces are _not_ part of the variable, but the print statement. If you access variables inside tags don’t put the braces around them.

If a variable or attribute does not exist, you will get back an undefined value. What you can do with that kind of value depends on the application configuration: the default behavior is to evaluate to an empty string if printed or iterated over, and to fail for every other operation.

Implementation

For the sake of convenience, `foo.bar` in Jinja does the following things on the Python layer:

-   check for an attribute called `bar` on `foo` (`getattr(foo, 'bar')`)
    
-   if there is not, check for an item `'bar'` in `foo` (`foo.__getitem__('bar')`)
    
-   if there is not, return an undefined object.
    

`foo['bar']` works mostly the same with a small difference in sequence:

-   check for an item `'bar'` in `foo`. (`foo.__getitem__('bar')`)
    
-   if there is not, check for an attribute called `bar` on `foo`. (`getattr(foo, 'bar')`)
    
-   if there is not, return an undefined object.
    

This is important if an object has an item and attribute with the same name. Additionally, the `attr()` filter only looks up attributes.

## Filters

Variables can be modified by **filters**. Filters are separated from the variable by a pipe symbol (`|`) and may have optional arguments in parentheses. Multiple filters can be chained. The output of one filter is applied to the next.

For example, `{{ name|striptags|title }}` will remove all HTML Tags from variable `name` and title-case the output (`title(striptags(name))`).

Filters that accept arguments have parentheses around the arguments, just like a function call. For example: `{{ listx|join(', ') }}` will join a list with commas (`str.join(', ', listx)`).

The [List of Builtin Filters](https://jinja.palletsprojects.com/en/latest/templates/#builtin-filters) below describes all the builtin filters.

## Tests

Beside filters, there are also so-called “tests” available. Tests can be used to test a variable against a common expression. To test a variable or expression, you add `is` plus the name of the test after the variable. For example, to find out if a variable is defined, you can do `name is defined`, which will then return true or false depending on whether `name` is defined in the current template context.

Tests can accept arguments, too. If the test only takes one argument, you can leave out the parentheses. For example, the following two expressions do the same thing:

```jinja
{% if loop.index is divisibleby 3 %}
{% if loop.index is divisibleby(3) %}
```

The [List of Builtin Tests](https://jinja.palletsprojects.com/en/latest/templates/#builtin-tests) below describes all the builtin tests.

## Comments

To comment-out part of a line in a template, use the comment syntax which is by default set to `{# ... #}`. This is useful to comment out parts of the template for debugging or to add information for other template designers or yourself:

```jinja
{# note: commented-out template because we no longer use this
    {% for user in users %}
        ...
    {% endfor %}
#}
```

## Whitespace Control

In the default configuration:

-   a single trailing newline is stripped if present 
-   other whitespace (spaces, tabs, newlines etc.) is returned unchanged

If an application configures Jinja to `trim_blocks`, the first newline after a template tag is removed automatically (like in PHP). The `lstrip_blocks` option can also be set to strip tabs and spaces from the beginning of a line to the start of a block. (Nothing will be stripped if there are other characters before the start of the block.)

With both `trim_blocks` and `lstrip_blocks` enabled, you can put block tags on their own lines, and the entire block line will be removed when rendered, preserving the whitespace of the contents. For example, without the `trim_blocks` and `lstrip_blocks` options, this template:

```html
<div>
    {% if True %}
        yay
    {% endif %}
</div>
```

gets rendered with blank lines inside the div:

```html
<div>

        yay

</div>
```

But with both `trim_blocks` and `lstrip_blocks` enabled, the template block lines are removed and other whitespace is preserved:

```html
<div>
        yay
</div>
```

You can manually disable the `lstrip_blocks` behavior by putting a plus sign (`+`) at the start of a block:

```jinja
<div>
        {%+ if something %}yay{% endif %}
</div>
```

Similarly, you can manually disable the `trim_blocks` behavior by putting a plus sign (`+`) at the end of a block:

```
<div>
    {% if something +%}
        yay
    {% endif %}
</div>
```

You can also strip whitespace in templates by hand. If you add a minus sign (`-`) to the start or end of a block (e.g. a [For](https://jinja.palletsprojects.com/en/latest/templates/#for-loop) tag), a comment, or a variable expression, the whitespaces before or after that block will be removed:

```
{% for item in seq -%}
    {{ item }}
{%- endfor %}
```

This will yield all elements without whitespace between them. If `seq` was a list of numbers from `1` to `9`, the output would be `123456789`.

If [Line Statements](https://jinja.palletsprojects.com/en/latest/templates/#line-statements) are enabled, they strip leading whitespace automatically up to the beginning of the line.

By default, Jinja also removes trailing newlines. To keep single trailing newlines, configure Jinja to `keep_trailing_newline`.

Note

You must not add whitespace between the tag and the minus sign.

**valid**:

```
{%- if foo -%}...{% endif %}
```

**invalid**:

```
{% - if foo - %}...{% endif %}
```

## Escaping

It is sometimes desirable – even necessary – to have Jinja ignore parts it would otherwise handle as variables or blocks. For example, if, with the default syntax, you want to use `{{` as a raw string in a template and not start a variable, you have to use a trick.

The easiest way to output a literal variable delimiter (`{{`) is by using a variable expression:

```jinja
{{ '{{' }}
```

For bigger sections, it makes sense to mark a block `raw`. For example, to include example Jinja syntax in a template, you can use this snippet:

```
{% raw %}
    <ul>
    {% for item in seq %}
        <li>{{ item }}</li>
    {% endfor %}
    </ul>
{% endraw %}
```

Note

Minus sign at the end of `{% raw -%}` tag cleans all the spaces and newlines preceding the first character of your raw data.

## Line Statements

If line statements are enabled by the application, it’s possible to mark a line as a statement. For example, if the line statement prefix is configured to `#`, the following two examples are equivalent:

```
<ul>
# for item in seq
    <li>{{ item }}</li>
# endfor
</ul>

<ul>
{% for item in seq %}
    <li>{{ item }}</li>
{% endfor %}
</ul>
```

The line statement prefix can appear anywhere on the line as long as no text precedes it. For better readability, statements that start a block (such as `for`, `if`, `elif` etc.) may end with a colon:

```
# for item in seq:
    ...
# endfor
```

Note

Line statements can span multiple lines if there are open parentheses, braces or brackets:

```
<ul>
# for href, caption in [('index.html', 'Index'),
                        ('about.html', 'About')]:
    <li><a href="{{ href }}">{{ caption }}</a></li>
# endfor
</ul>
```

Since Jinja 2.2, line-based comments are available as well. For example, if the line-comment prefix is configured to be `##`, everything from `##` to the end of the line is ignored (excluding the newline sign):

```
# for item in seq:
    <li>{{ item }}</li>     ## this comment is ignored
# endfor
```

## Template Inheritance

The most powerful part of Jinja is template inheritance. Template inheritance allows you to build a base “skeleton” template that contains all the common elements of your site and defines **blocks** that child templates can override.

Sounds complicated but is very basic. It’s easiest to understand it by starting with an example.

### Base Template

This template, which we’ll call `base.html`, defines a simple HTML skeleton document that you might use for a simple two-column page. It’s the job of “child” templates to fill the empty blocks with content:

```
<!DOCTYPE html>
<html lang="en">
<head>
    {% block head %}
    <link rel="stylesheet" href="style.css" />
    <title>{% block title %}{% endblock %} - My Webpage</title>
    {% endblock %}
</head>
<body>
    <div id="content">{% block content %}{% endblock %}</div>
    <div id="footer">
        {% block footer %}
        &copy; Copyright 2008 by <a href="http://domain.invalid/">you</a>.
        {% endblock %}
    </div>
</body>
</html>
```

In this example, the `{% block %}` tags define four blocks that child templates can fill in. All the `block` tag does is tell the template engine that a child template may override those placeholders in the template.

`block` tags can be inside other blocks such as `if`, but they will always be executed regardless of if the `if` block is actually rendered.

### Child Template

A child template might look like this:

```
{% extends "base.html" %}
{% block title %}Index{% endblock %}
{% block head %}
    {{ super() }}
    <style type="text/css">
        .important { color: #336699; }
    </style>
{% endblock %}
{% block content %}
    <h1>Index</h1>
    <p class="important">
      Welcome to my awesome homepage.
    </p>
{% endblock %}
```

The `{% extends %}` tag is the key here. It tells the template engine that this template “extends” another template. When the template system evaluates this template, it first locates the parent. The extends tag should be the first tag in the template. Everything before it is printed out normally and may cause confusion. For details about this behavior and how to take advantage of it, see [Null-Default Fallback](https://jinja.palletsprojects.com/en/latest/tricks/#null-default-fallback). Also a block will always be filled in regardless of whether the surrounding condition is evaluated to be true or false.

The filename of the template depends on the template loader. For example, the [`FileSystemLoader`](https://jinja.palletsprojects.com/en/latest/api/#jinja2.FileSystemLoader "jinja2.FileSystemLoader") allows you to access other templates by giving the filename. You can access templates in subdirectories with a slash:

```
{% extends "layout/default.html" %}
```

But this behavior can depend on the application embedding Jinja. Note that since the child template doesn’t define the `footer` block, the value from the parent template is used instead.

You can’t define multiple `{% block %}` tags with the same name in the same template. This limitation exists because a block tag works in “both” directions. That is, a block tag doesn’t just provide a placeholder to fill - it also defines the content that fills the placeholder in the _parent_. If there were two similarly-named `{% block %}` tags in a template, that template’s parent wouldn’t know which one of the blocks’ content to use.

If you want to print a block multiple times, you can, however, use the special `self` variable and call the block with that name:

```
<title>{% block title %}{% endblock %}</title>
<h1>{{ self.title() }}</h1>
{% block body %}{% endblock %}
```

### Super Blocks

It’s possible to render the contents of the parent block by calling `super()`. This gives back the results of the parent block:

```
{% block sidebar %}
    <h3>Table Of Contents</h3>
    ...
    {{ super() }}
{% endblock %}
```

### Nesting extends

In the case of multiple levels of `{% extends %}`, `super` references may be chained (as in `super.super()`) to skip levels in the inheritance tree.

For example:

```
# parent.tmpl
body: {% block body %}Hi from parent.{% endblock %}

# child.tmpl
{% extends "parent.tmpl" %}
{% block body %}Hi from child. {{ super() }}{% endblock %}

# grandchild1.tmpl
{% extends "child.tmpl" %}
{% block body %}Hi from grandchild1.{% endblock %}

# grandchild2.tmpl
{% extends "child.tmpl" %}
{% block body %}Hi from grandchild2. {{ super.super() }} {% endblock %}
```

Rendering `child.tmpl` will give `body: Hi from child. Hi from parent.`

Rendering `grandchild1.tmpl` will give `body: Hi from grandchild1.`

Rendering `grandchild2.tmpl` will give `body: Hi from grandchild2. Hi from parent.`

### Named Block End-Tags

Jinja allows you to put the name of the block after the end tag for better readability:

```
{% block sidebar %}
    {% block inner_sidebar %}
        ...
    {% endblock inner_sidebar %}
{% endblock sidebar %}
```

However, the name after the `endblock` word must match the block name.

### Block Nesting and Scope

Blocks can be nested for more complex layouts. However, per default blocks may not access variables from outer scopes:

```
{% for item in seq %}
    <li>{% block loop_item %}{{ item }}{% endblock %}</li>
{% endfor %}
```

This example would output empty `<li>` items because `item` is unavailable inside the block. The reason for this is that if the block is replaced by a child template, a variable would appear that was not defined in the block or passed to the context.

Starting with Jinja 2.2, you can explicitly specify that variables are available in a block by setting the block to “scoped” by adding the `scoped` modifier to a block declaration:

```
{% for item in seq %}
    <li>{% block loop_item scoped %}{{ item }}{% endblock %}</li>
{% endfor %}
```

When overriding a block, the `scoped` modifier does not have to be provided.

### Required Blocks

Blocks can be marked as `required`. They must be overridden at some point, but not necessarily by the direct child template. Required blocks may only contain space and comments, and they cannot be rendered directly.

`page.txt`

```
{% extends "page.txt" %}
```

`issue.txt`

```
{% extends "page.txt" %}
```

`bug_report.txt`

```
{% extends "issue.txt" %}
{% block body %}Provide steps to demonstrate the bug.{% endblock %}
```

Rendering `page.txt` or `issue.txt` will raise `TemplateRuntimeError` because they don’t override the `body` block. Rendering `bug_report.txt` will succeed because it does override the block.

When combined with `scoped`, the `required` modifier must be placed _after_ the scoped modifier. Here are some valid examples:

```
{% block body scoped %}{% endblock %}
{% block body required %}{% endblock %}
{% block body scoped required %}{% endblock %}
```

### Template Objects

`extends`, `include`, and `import` can take a template object instead of the name of a template to load. This could be useful in some advanced situations, since you can use Python code to load a template first and pass it in to `render`.

```
if debug_mode:
    layout = env.get_template("debug_layout.html")
else:
    layout = env.get_template("layout.html")

user_detail = env.get_template("user/detail.html")
return user_detail.render(layout=layout)
```

```
{% extends layout %}
```

Note how `extends` is passed the variable with the template object that was passed to `render`, instead of a string.

## HTML Escaping

When generating HTML from templates, there’s always a risk that a variable will include characters that affect the resulting HTML. There are two approaches:

1.  manually escaping each variable; or
    
2.  automatically escaping everything by default.
    

Jinja supports both. What is used depends on the application configuration. The default configuration is no automatic escaping; for various reasons:

-   Escaping everything except for safe values will also mean that Jinja is escaping variables known to not include HTML (e.g. numbers, booleans) which can be a huge performance hit.
    
-   The information about the safety of a variable is very fragile. It could happen that by coercing safe and unsafe values, the return value is double-escaped HTML.
    

### Working with Manual Escaping

If manual escaping is enabled, it’s **your** responsibility to escape variables if needed. What to escape? If you have a variable that _may_ include any of the following chars (`>`, `<`, `&`, or `"`) you **SHOULD** escape it unless the variable contains well-formed and trusted HTML. Escaping works by piping the variable through the `|e` filter:

```
{{ user.username|e }}
```

### Working with Automatic Escaping

When automatic escaping is enabled, everything is escaped by default except for values explicitly marked as safe. Variables and expressions can be marked as safe either in:

1.  The context dictionary by the application with `markupsafe.Markup`
    
2.  The template, with the `|safe` filter.
    

If a string that you marked safe is passed through other Python code that doesn’t understand that mark, it may get lost. Be aware of when your data is marked safe and how it is processed before arriving at the template.

If a value has been escaped but is not marked safe, auto-escaping will still take place and result in double-escaped characters. If you know you have data that is already safe but not marked, be sure to wrap it in `Markup` or use the `|safe` filter.

Jinja functions (macros, `super`, `self.BLOCKNAME`) always return template data that is marked as safe.

String literals in templates with automatic escaping are considered unsafe because native Python strings are not safe.

## List of Control Structures

A control structure refers to all those things that control the flow of a program - conditionals (i.e. if/elif/else), for-loops, as well as things like macros and blocks. With the default syntax, control structures appear inside `{% ... %}` blocks.

### For

Loop over each item in a sequence. For example, to display a list of users provided in a variable called `users`:

```
<h1>Members</h1>
<ul>
{% for user in users %}
  <li>{{ user.username|e }}</li>
{% endfor %}
</ul>
```

As variables in templates retain their object properties, it is possible to iterate over containers like `dict`:

```
<dl>
{% for key, value in my_dict.items() %}
    <dt>{{ key|e }}</dt>
    <dd>{{ value|e }}</dd>
{% endfor %}
</dl>
```

Python dicts may not be in the order you want to display them in. If order matters, use the `|dictsort` filter.

```
<dl>
{% for key, value in my_dict | dictsort %}
    <dt>{{ key|e }}</dt>
    <dd>{{ value|e }}</dd>
{% endfor %}
</dl>
```

Inside of a for-loop block, you can access some special variables:

| Variable         | Description                                                   |
|------------------|---------------------------------------------------------------|
| `loop.index`     | The current iteration of the loop. (1 indexed)                |
| `loop.index0`    | The current iteration of the loop. (0 indexed)                |
| `loop.revindex`  | The number of iterations from the end of the loop (1 indexed) |
| `loop.revindex0` | The number of iterations from the end of the loop (0 indexed) |
| `loop.first`     | True if first iteration.                                      |
| `loop.last`      | True if last iteration.                                       |
| `loop.length`    | The number of items in the sequence. |
| `loop.cycle` | A helper function to cycle between a list of sequences. See the explanation below. |
| `loop.depth` | Indicates how deep in a recursive loop the rendering currently is. Starts at level 1 |
| `loop.depth0` | Indicates how deep in a recursive loop the rendering currently is. Starts at level 0 |
| `loop.previtem` | The item from the previous iteration of the loop. Undefined during the first iteration. |
| `loop.nextitem` | The item from the following iteration of the loop. Undefined during the last iteration. |
| `loop.changed(*val)` | True if previously called with a different value (or not called at all). |

Within a for-loop, it’s possible to cycle among a list of strings/variables each time through the loop by using the special `loop.cycle` helper:

```
{% for row in rows %}
    <li class="{{ loop.cycle('odd', 'even') }}">{{ row }}</li>
{% endfor %}
```

Since Jinja 2.1, an extra `cycle` helper exists that allows loop-unbound cycling. For more information, have a look at the [List of Global Functions](https://jinja.palletsprojects.com/en/latest/templates/#builtin-globals).

Unlike in Python, it’s not possible to `break` or `continue` in a loop. You can, however, filter the sequence during iteration, which allows you to skip items. The following example skips all the users which are hidden:

```
{% for user in users if not user.hidden %}
    <li>{{ user.username|e }}</li>
{% endfor %}
```

The advantage is that the special `loop` variable will count correctly; thus not counting the users not iterated over.

If no iteration took place because the sequence was empty or the filtering removed all the items from the sequence, you can render a default block by using `else`:

```
<ul>
{% for user in users %}
    <li>{{ user.username|e }}</li>
{% else %}
    <li><em>no users found</em></li>
{% endfor %}
</ul>
```

Note that, in Python, `else` blocks are executed whenever the corresponding loop **did not** `break`. Since Jinja loops cannot `break` anyway, a slightly different behavior of the `else` keyword was chosen.

It is also possible to use loops recursively. This is useful if you are dealing with recursive data such as sitemaps or RDFa. To use loops recursively, you basically have to add the `recursive` modifier to the loop definition and call the `loop` variable with the new iterable where you want to recurse.

The following example implements a sitemap with recursive loops:

```
<ul class="sitemap">
{%- for item in sitemap recursive %}
    <li><a href="{{ item.href|e }}">{{ item.title }}</a>
    {%- if item.children -%}
        <ul class="submenu">{{ loop(item.children) }}</ul>
    {%- endif %}</li>
{%- endfor %}
</ul>
```

The `loop` variable always refers to the closest (innermost) loop. If we have more than one level of loops, we can rebind the variable `loop` by writing `{% set outer_loop = loop %}` after the loop that we want to use recursively. Then, we can call it using `{{ outer_loop(...) }}`

Please note that assignments in loops will be cleared at the end of the iteration and cannot outlive the loop scope. Older versions of Jinja had a bug where in some circumstances it appeared that assignments would work. This is not supported. See [Assignments](https://jinja.palletsprojects.com/en/latest/templates/#assignments) for more information about how to deal with this.

If all you want to do is check whether some value has changed since the last iteration or will change in the next iteration, you can use `previtem` and `nextitem`:

```
{% for value in values %}
    {% if loop.previtem is defined and value > loop.previtem %}
        The value just increased!
    {% endif %}
    {{ value }}
    {% if loop.nextitem is defined and loop.nextitem > value %}
        The value will increase even more!
    {% endif %}
{% endfor %}
```

If you only care whether the value changed at all, using `changed` is even easier:

```
{% for entry in entries %}
    {% if loop.changed(entry.category) %}
        <h2>{{ entry.category }}</h2>
    {% endif %}
    <p>{{ entry.message }}</p>
{% endfor %}
```

### If

The `if` statement in Jinja is comparable with the Python if statement. In the simplest form, you can use it to test if a variable is defined, not empty and not false:

```
{% if users %}
<ul>
{% for user in users %}
    <li>{{ user.username|e }}</li>
{% endfor %}
</ul>
{% endif %}
```

For multiple branches, `elif` and `else` can be used like in Python. You can use more complex [Expressions](https://jinja.palletsprojects.com/en/latest/templates/#expressions) there, too:

```
{% if kenny.sick %}
    Kenny is sick.
{% elif kenny.dead %}
    You killed Kenny!  You bastard!!!
{% else %}
    Kenny looks okay --- so far
{% endif %}
```

If can also be used as an [inline expression](https://jinja.palletsprojects.com/en/latest/templates/#if-expression) and for [loop filtering](https://jinja.palletsprojects.com/en/latest/templates/#loop-filtering).

### Macros

Macros are comparable with functions in regular programming languages. They are useful to put often used idioms into reusable functions to not repeat yourself (“DRY”).

Here’s a small example of a macro that renders a form element:

```
{% macro input(name, value='', type='text', size=20) -%}
    <input type="{{ type }}" name="{{ name }}" value="{{
        value|e }}" size="{{ size }}">
{%- endmacro %}
```

The macro can then be called like a function in the namespace:

```
<p>{{ input('username') }}</p>
<p>{{ input('password', type='password') }}</p>
```

If the macro was defined in a different template, you have to [import](https://jinja.palletsprojects.com/en/latest/templates/#import) it first.

Inside macros, you have access to three special variables:

`varargs`

If more positional arguments are passed to the macro than accepted by the macro, they end up in the special `varargs` variable as a list of values.

`kwargs`

Like `varargs` but for keyword arguments. All unconsumed keyword arguments are stored in this special variable.

`caller`

If the macro was called from a [call](https://jinja.palletsprojects.com/en/latest/templates/#call) tag, the caller is stored in this variable as a callable macro.

Macros also expose some of their internal details. The following attributes are available on a macro object:

`name`

The name of the macro. `{{ input.name }}` will print `input`.

`arguments`

A tuple of the names of arguments the macro accepts.

`catch_kwargs`

This is `true` if the macro accepts extra keyword arguments (i.e.: accesses the special `kwargs` variable).

`catch_varargs`

This is `true` if the macro accepts extra positional arguments (i.e.: accesses the special `varargs` variable).

`caller`

This is `true` if the macro accesses the special `caller` variable and may be called from a [call](https://jinja.palletsprojects.com/en/latest/templates/#call) tag.

If a macro name starts with an underscore, it’s not exported and can’t be imported.

Due to how scopes work in Jinja, a macro in a child template does not override a macro in a parent template. The following will output “LAYOUT”, not “CHILD”.

`layout.txt`

```
{% macro foo() %}LAYOUT{% endmacro %}
{% block body %}{% endblock %}
```

`child.txt`

```
{% extends 'layout.txt' %}
{% macro foo() %}CHILD{% endmacro %}
{% block body %}{{ foo() }}{% endblock %}
```

### Call

In some cases it can be useful to pass a macro to another macro. For this purpose, you can use the special `call` block. The following example shows a macro that takes advantage of the call functionality and how it can be used:

```
{% macro render_dialog(title, class='dialog') -%}
    <div class="{{ class }}">
        <h2>{{ title }}</h2>
        <div class="contents">
            {{ caller() }}
        </div>
    </div>
{%- endmacro %}

{% call render_dialog('Hello World') %}
    This is a simple dialog rendered by using a macro and
    a call block.
{% endcall %}
```

It’s also possible to pass arguments back to the call block. This makes it useful as a replacement for loops. Generally speaking, a call block works exactly like a macro without a name.

Here’s an example of how a call block can be used with arguments:

```
{% macro dump_users(users) -%}
    <ul>
    {%- for user in users %}
        <li><p>{{ user.username|e }}</p>{{ caller(user) }}</li>
    {%- endfor %}
    </ul>
{%- endmacro %}

{% call(user) dump_users(list_of_user) %}
    <dl>
        <dt>Realname</dt>
        <dd>{{ user.realname|e }}</dd>
        <dt>Description</dt>
        <dd>{{ user.description }}</dd>
    </dl>
{% endcall %}
```

### Filters

Filter sections allow you to apply regular Jinja filters on a block of template data. Just wrap the code in the special `filter` section:

```
{% filter upper %}
    This text becomes uppercase
{% endfilter %}
```

Filters that accept arguments can be called like this:

```
{% filter center(100) %}Center this{% endfilter %}
```

### Assignments

Inside code blocks, you can also assign values to variables. Assignments at top level (outside of blocks, macros or loops) are exported from the template like top level macros and can be imported by other templates.

Assignments use the `set` tag and can have multiple targets:

```
{% set navigation = [('index.html', 'Index'), ('about.html', 'About')] %}
{% set key, value = call_something() %}
```

Scoping Behavior

Please keep in mind that it is not possible to set variables inside a block and have them show up outside of it. This also applies to loops. The only exception to that rule are if statements which do not introduce a scope. As a result the following template is not going to do what you might expect:

```
{% set iterated = false %}
{% for item in seq %}
    {{ item }}
    {% set iterated = true %}
{% endfor %}
{% if not iterated %} did not iterate {% endif %}
```

It is not possible with Jinja syntax to do this. Instead use alternative constructs like the loop else block or the special `loop` variable:

```
{% for item in seq %}
    {{ item }}
{% else %}
    did not iterate
{% endfor %}
```

As of version 2.10 more complex use cases can be handled using namespace objects which allow propagating of changes across scopes:

```
{% set ns = namespace(found=false) %}
{% for item in items %}
    {% if item.check_something() %}
        {% set ns.found = true %}
    {% endif %}
    * {{ item.title }}
{% endfor %}
Found item having something: {{ ns.found }}
```

Note that the `obj.attr` notation in the `set` tag is only allowed for namespace objects; attempting to assign an attribute on any other object will raise an exception.

Changelog

Added in version 2.10: Added support for namespace objects

### Block Assignments

Changelog

Added in version 2.8.

Starting with Jinja 2.8, it’s possible to also use block assignments to capture the contents of a block into a variable name. This can be useful in some situations as an alternative for macros. In that case, instead of using an equals sign and a value, you just write the variable name and then everything until `{% endset %}` is captured.

Example:

```
{% set navigation %}
    <li><a href="/">Index</a>
    <li><a href="/downloads">Downloads</a>
{% endset %}
```

The `navigation` variable then contains the navigation HTML source.

Changelog

Changed in version 2.10.

Starting with Jinja 2.10, the block assignment supports filters.

Example:

```
{% set reply | wordwrap %}
    You wrote:
    {{ message }}
{% endset %}
```

### Extends

The `extends` tag can be used to extend one template from another. You can have multiple `extends` tags in a file, but only one of them may be executed at a time.

See the section about [Template Inheritance](https://jinja.palletsprojects.com/en/latest/templates/#template-inheritance) above.

### Blocks

Blocks are used for inheritance and act as both placeholders and replacements at the same time. They are documented in detail in the [Template Inheritance](https://jinja.palletsprojects.com/en/latest/templates/#template-inheritance) section.

### Include

The `include` tag renders another template and outputs the result into the current template.

```
{% include 'header.html' %}
Body goes here.
{% include 'footer.html' %}
```

The included template has access to context of the current template by default. Use `without context` to use a separate context instead. `with context` is also valid, but is the default behavior. See [Import Context Behavior](https://jinja.palletsprojects.com/en/latest/templates/#import-visibility).

The included template can `extend` another template and override blocks in that template. However, the current template cannot override any blocks that the included template outputs.

Use `ignore missing` to ignore the statement if the template does not exist. It must be placed _before_ a context visibility statement.

```
{% include "sidebar.html" without context %}
{% include "sidebar.html" ignore missing %}
{% include "sidebar.html" ignore missing with context %}
{% include "sidebar.html" ignore missing without context %}
```

If a list of templates is given, each will be tried in order until one is not missing. This can be used with `ignore missing` to ignore if none of the templates exist.

```
{% include ['page_detailed.html', 'page.html'] %}
{% include ['special_sidebar.html', 'sidebar.html'] ignore missing %}
```

A variable, with either a template name or template object, can also be passed to the statement.

### Import

Jinja supports putting often used code into macros. These macros can go into different templates and get imported from there. This works similarly to the import statements in Python. It’s important to know that imports are cached and imported templates don’t have access to the current template variables, just the globals by default. For more details about context behavior of imports and includes, see [Import Context Behavior](https://jinja.palletsprojects.com/en/latest/templates/#import-visibility).

There are two ways to import templates. You can import a complete template into a variable or request specific macros / exported variables from it.

Imagine we have a helper module that renders forms (called `forms.html`):

```
{% macro input(name, value='', type='text') -%}
    <input type="{{ type }}" value="{{ value|e }}" name="{{ name }}">
{%- endmacro %}

{%- macro textarea(name, value='', rows=10, cols=40) -%}
    <textarea name="{{ name }}" rows="{{ rows }}" cols="{{ cols
        }}">{{ value|e }}</textarea>
{%- endmacro %}
```

The easiest and most flexible way to access a template’s variables and macros is to import the whole template module into a variable. That way, you can access the attributes:

```
{% import 'forms.html' as forms %}
<dl>
    <dt>Username</dt>
    <dd>{{ forms.input('username') }}</dd>
    <dt>Password</dt>
    <dd>{{ forms.input('password', type='password') }}</dd>
</dl>
<p>{{ forms.textarea('comment') }}</p>
```

Alternatively, you can import specific names from a template into the current namespace:

```
{% from 'forms.html' import input as input_field, textarea %}
<dl>
    <dt>Username</dt>
    <dd>{{ input_field('username') }}</dd>
    <dt>Password</dt>
    <dd>{{ input_field('password', type='password') }}</dd>
</dl>
<p>{{ textarea('comment') }}</p>
```

Macros and variables starting with one or more underscores are private and cannot be imported.

Changelog

Changed in version 2.4: If a template object was passed to the template context, you can import from that object.

## Import Context Behavior

By default, included templates are passed the current context and imported templates are not. The reason for this is that imports, unlike includes, are cached; as imports are often used just as a module that holds macros.

This behavior can be changed explicitly: by adding `with context` or `without context` to the import/include directive, the current context can be passed to the template and caching is disabled automatically.

Here are two examples:

```
{% from 'forms.html' import input with context %}
{% include 'header.html' without context %}
```

Note

In Jinja 2.0, the context that was passed to the included template did not include variables defined in the template. As a matter of fact, this did not work:

```
{% for box in boxes %}
    {% include "render_box.html" %}
{% endfor %}
```

The included template `render_box.html` is _not_ able to access `box` in Jinja 2.0. As of Jinja 2.1, `render_box.html` _is_ able to do so.

## Expressions

Jinja allows basic expressions everywhere. These work very similarly to regular Python; even if you’re not working with Python you should feel comfortable with it.

### Literals

The simplest form of expressions are literals. Literals are representations for Python objects such as strings and numbers. The following literals exist:

`"Hello World"`

Everything between two double or single quotes is a string. They are useful whenever you need a string in the template (e.g. as arguments to function calls and filters, or just to extend or include a template).

`42` / `123_456`

Integers are whole numbers without a decimal part. The ‘\_’ character can be used to separate groups for legibility.

`42.23` / `42.1e2` / `123_456.789`

Floating point numbers can be written using a ‘.’ as a decimal mark. They can also be written in scientific notation with an upper or lower case ‘e’ to indicate the exponent part. The ‘\_’ character can be used to separate groups for legibility, but cannot be used in the exponent part.

`['list', 'of', 'objects']`

Everything between two brackets is a list. Lists are useful for storing sequential data to be iterated over. For example, you can easily create a list of links using lists and tuples for (and with) a for loop:

```
<ul>
{% for href, caption in [('index.html', 'Index'), ('about.html', 'About'),
                         ('downloads.html', 'Downloads')] %}
    <li><a href="{{ href }}">{{ caption }}</a></li>
{% endfor %}
</ul>
```

`('tuple', 'of', 'values')`

Tuples are like lists that cannot be modified (“immutable”). If a tuple only has one item, it must be followed by a comma (`('1-tuple',)`). Tuples are usually used to represent items of two or more elements. See the list example above for more details.

`{'dict': 'of', 'key': 'and', 'value': 'pairs'}`

A dict in Python is a structure that combines keys and values. Keys must be unique and always have exactly one value. Dicts are rarely used in templates; they are useful in some rare cases such as the `xmlattr()` filter.

`true` / `false`

`true` is always true and `false` is always false.

Note

The special constants `true`, `false`, and `none` are indeed lowercase. Because that caused confusion in the past, (`True` used to expand to an undefined variable that was considered false), all three can now also be written in title case (`True`, `False`, and `None`). However, for consistency, (all Jinja identifiers are lowercase) you should use the lowercase versions.

### Math

Jinja allows you to calculate with values. This is rarely useful in templates but exists for completeness’ sake. The following operators are supported:

`+`

Adds two objects together. Usually the objects are numbers, but if both are strings or lists, you can concatenate them this way. This, however, is not the preferred way to concatenate strings! For string concatenation, have a look-see at the `~` operator. `{{ 1 + 1 }}` is `2`.

`-`

Subtract the second number from the first one. `{{ 3 - 2 }}` is `1`.

`/`

Divide two numbers. The return value will be a floating point number. `{{ 1 / 2 }}` is `{{ 0.5 }}`.

`//`

Divide two numbers and return the truncated integer result. `{{ 20 // 7 }}` is `2`.

`%`

Calculate the remainder of an integer division. `{{ 11 % 7 }}` is `4`.

`*`

Multiply the left operand with the right one. `{{ 2 * 2 }}` would return `4`. This can also be used to repeat a string multiple times. `{{ '=' * 80 }}` would print a bar of 80 equal signs.

`**`

Raise the left operand to the power of the right operand. `{{ 2**3 }}` would return `8`.

Unlike Python, chained pow is evaluated left to right. `{{ 3**3**3 }}` is evaluated as `(3**3)**3` in Jinja, but would be evaluated as `3**(3**3)` in Python. Use parentheses in Jinja to be explicit about what order you want. It is usually preferable to do extended math in Python and pass the results to `render` rather than doing it in the template.

This behavior may be changed in the future to match Python, if it’s possible to introduce an upgrade path.

### Comparisons

`==`

Compares two objects for equality.

`!=`

Compares two objects for inequality.

`>`

`true` if the left hand side is greater than the right hand side.

`>=`

`true` if the left hand side is greater or equal to the right hand side.

`<`

`true` if the left hand side is lower than the right hand side.

`<=`

`true` if the left hand side is lower or equal to the right hand side.

### Logic

For `if` statements, `for` filtering, and `if` expressions, it can be useful to combine multiple expressions:

`and`

Return true if the left and the right operand are true.

`or`

Return true if the left or the right operand are true.

`not`

negate a statement (see below).

`(expr)`

Parentheses group an expression.

Note

The `is` and `in` operators support negation using an infix notation, too: `foo is not bar` and `foo not in bar` instead of `not foo is bar` and `not foo in bar`. All other expressions require a prefix notation: `not (foo and bar).`

### Other Operators

The following operators are very useful but don’t fit into any of the other two categories:

`in`

Perform a sequence / mapping containment test. Returns true if the left operand is contained in the right. `{{ 1 in [1, 2, 3] }}` would, for example, return true.

`is`

Performs a [test](https://jinja.palletsprojects.com/en/latest/templates/#tests).

`|` (pipe, vertical bar)

Applies a [filter](https://jinja.palletsprojects.com/en/latest/templates/#filters).

`~` (tilde)

Converts all operands into strings and concatenates them.

`{{ "Hello " ~ name ~ "!" }}` would return (assuming `name` is set to `'John'`) `Hello John!`.

`()`

Call a callable: `{{ post.render() }}`. Inside of the parentheses you can use positional arguments and keyword arguments like in Python:

`{{ post.render(user, full=true) }}`.

`.` / `[]`

Get an attribute of an object. (See [Variables](https://jinja.palletsprojects.com/en/latest/templates/#variables))

### If Expression

It is also possible to use inline `if` expressions. These are useful in some situations. For example, you can use this to extend from one template if a variable is defined, otherwise from the default layout template:

```
{% extends layout_template if layout_template is defined else 'default.html' %}
```

The general syntax is `<do something> if <something is true> else <do something else>`.

The `else` part is optional. If not provided, the else block implicitly evaluates into an [`Undefined`](https://jinja.palletsprojects.com/en/latest/api/#jinja2.Undefined "jinja2.Undefined") object (regardless of what `undefined` in the environment is set to):

```
{{ "[{}]".format(page.title) if page.title }}
```

### Python Methods

You can also use any of the methods defined on a variable’s type. The value returned from the method invocation is used as the value of the expression. Here is an example that uses methods defined on strings (where `page.title` is a string):

```
{{ page.title.capitalize() }}
```

This works for methods on user-defined types. For example, if variable `f` of type `Foo` has a method `bar` defined on it, you can do the following:

```
{{ f.bar(value) }}
```

Operator methods also work as expected. For example, `%` implements printf-style for strings:

```
{{ "Hello, %s!" % name }}
```

Although you should prefer the `.format` method for that case (which is a bit contrived in the context of rendering a template):

```
{{ "Hello, {}!".format(name) }}
```

## List of Builtin Filters

jinja-filters.abs(_x_, _/_)

Return the absolute value of the argument.

jinja-filters.attr(_obj: Any_, _name: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [jinja2.runtime.Undefined](https://jinja.palletsprojects.com/en/latest/api/#jinja2.Undefined "jinja2.runtime.Undefined") | Any

Get an attribute of an object. `foo|attr("bar")` works like `foo.bar` just that always an attribute is returned and items are not looked up.

See [Notes on subscriptions](https://jinja.palletsprojects.com/en/latest/templates/#notes-on-subscriptions) for more details.

jinja-filters.batch(_value: 't.Iterable\[V\]'_, _linecount: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_, _fill\_with: 't.Optional\[V\]' \= None_) → 't.Iterator\[t.List\[V\]\]'

A filter that batches items. It works pretty much like `slice` just the other way round. It returns a list of lists with the given number of items. If you provide a second parameter this is used to fill up missing items. See this example:

```
<table>
{%- for row in items|batch(3, '&nbsp;') %}
  <tr>
  {%- for column in row %}
    <td>{{ column }}</td>
  {%- endfor %}
  </tr>
{%- endfor %}
</table>
```

jinja-filters.capitalize(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Capitalize a value. The first character will be uppercase, all others lowercase.

jinja-filters.center(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _width: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") \= 80_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Centers the value in a field of a given width.

jinja-filters.default(_value: V_, _default\_value: V \= ''_, _boolean: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_) → V

If the value is undefined it will return the passed default value, otherwise the value of the variable:

```
{{ my_variable|default('my_variable is not defined') }}
```

This will output the value of `my_variable` if the variable was defined, otherwise `'my_variable is not defined'`. If you want to use default with variables that evaluate to false you have to set the second parameter to `true`:

```
{{ ''|default('the string was empty', true) }}
```

Changelog

Changed in version 2.11: It’s now possible to configure the [`Environment`](https://jinja.palletsprojects.com/en/latest/api/#jinja2.Environment "jinja2.Environment") with [`ChainableUndefined`](https://jinja.palletsprojects.com/en/latest/api/#jinja2.ChainableUndefined "jinja2.ChainableUndefined") to make the `default` filter work on nested elements and attributes that may contain undefined values in the chain without getting an [`UndefinedError`](https://jinja.palletsprojects.com/en/latest/api/#jinja2.UndefinedError "jinja2.UndefinedError").

Aliases:

`d`

jinja-filters.dictsort(_value: Mapping\[K, V\]_, _case\_sensitive: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _by: 'te.Literal\["key", "value"\]' \= 'key'_, _reverse: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_) → [List](https://jinja.palletsprojects.com/en/latest/extensions/#jinja2.nodes.List "jinja2.nodes.List")\[[Tuple](https://jinja.palletsprojects.com/en/latest/extensions/#jinja2.nodes.Tuple "jinja2.nodes.Tuple")\[K, V\]\]

Sort a dict and yield (key, value) pairs. Python dicts may not be in the order you want to display them in, so sort them first.

```
{% for key, value in mydict|dictsort %}
    sort the dict by key, case insensitive

{% for key, value in mydict|dictsort(reverse=true) %}
    sort the dict by key, case insensitive, reverse order

{% for key, value in mydict|dictsort(true) %}
    sort the dict by key, case sensitive

{% for key, value in mydict|dictsort(false, 'value') %}
    sort the dict by value, case insensitive
```

jinja-filters.escape(_value_)

Replace the characters `&`, `<`, `>`, `'`, and `"` in the string with HTML-safe sequences. Use this if you need to display text that might contain such characters in HTML.

If the object has an `__html__` method, it is called and the return value is assumed to already be safe for HTML.

Parameters:

**s** – An object to be converted to a string and escaped.

Returns:

A `Markup` string with the escaped text.

Aliases:

`e`

jinja-filters.filesizeformat(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [float](https://docs.python.org/3/library/functions.html#float "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_, _binary: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Format the value like a ‘human-readable’ file size (i.e. 13 kB, 4.1 MB, 102 Bytes, etc). Per default decimal prefixes are used (Mega, Giga, etc.), if the second parameter is set to `True` the binary prefixes are used (Mebi, Gibi).

jinja-filters.first(_seq: 't.Iterable\[V\]'_) → 't.Union\[V, Undefined\]'

Return the first item of a sequence.

jinja-filters.float(_value: Any_, _default: [float](https://docs.python.org/3/library/functions.html#float "(in Python v3.12)") \= 0.0_) → [float](https://docs.python.org/3/library/functions.html#float "(in Python v3.12)")

Convert the value into a floating point number. If the conversion doesn’t work it will return `0.0`. You can override this default using the first parameter.

jinja-filters.forceescape(_value: 't.Union\[str, HasHTML\]'_) → markupsafe.Markup

Enforce HTML escaping. This will probably double escape variables.

jinja-filters.format(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _\*args: Any_, _\*\*kwargs: Any_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Apply the given values to a [printf-style](https://docs.python.org/library/stdtypes.html#printf-style-string-formatting) format string, like `string % values`.

```
{{ "%s, %s!"|format(greeting, name) }}
Hello, World!
```

In most cases it should be more convenient and efficient to use the `%` operator or [`str.format()`](https://docs.python.org/3/library/stdtypes.html#str.format "(in Python v3.12)").

```
{{ "%s, %s!" % (greeting, name) }}
{{ "{}, {}!".format(greeting, name) }}
```

jinja-filters.groupby(_value: 't.Iterable\[V\]'_, _attribute: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_, _default: Any | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_, _case\_sensitive: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_) → 't.List\[\_GroupTuple\]'

Group a sequence of objects by an attribute using Python’s [`itertools.groupby()`](https://docs.python.org/3/library/itertools.html#itertools.groupby "(in Python v3.12)"). The attribute can use dot notation for nested access, like `"address.city"`. Unlike Python’s `groupby`, the values are sorted first so only one group is returned for each unique value.

For example, a list of `User` objects with a `city` attribute can be rendered in groups. In this example, `grouper` refers to the `city` value of the group.

```
<ul>{% for city, items in users|groupby("city") %}
  <li>{{ city }}
    <ul>{% for user in items %}
      <li>{{ user.name }}
    {% endfor %}</ul>
  </li>
{% endfor %}</ul>
```

`groupby` yields namedtuples of `(grouper, list)`, which can be used instead of the tuple unpacking above. `grouper` is the value of the attribute, and `list` is the items with that value.

```
<ul>{% for group in users|groupby("city") %}
  <li>{{ group.grouper }}: {{ group.list|join(", ") }}
{% endfor %}</ul>
```

You can specify a `default` value to use if an object in the list does not have the given attribute.

```
<ul>{% for city, items in users|groupby("city", default="NY") %}
  <li>{{ city }}: {{ items|map(attribute="name")|join(", ") }}</li>
{% endfor %}</ul>
```

Like the [`sort()`](https://jinja.palletsprojects.com/en/latest/templates/#jinja-filters.sort "jinja-filters.sort") filter, sorting and grouping is case-insensitive by default. The `key` for each group will have the case of the first item in that group of values. For example, if a list of users has cities `["CA", "NY", "ca"]`, the “CA” group will have two values. This can be disabled by passing `case_sensitive=True`.

Changelog

Changed in version 3.1: Added the `case_sensitive` parameter. Sorting and grouping is case-insensitive by default, matching other filters that do comparisons.

Changed in version 3.0: Added the `default` parameter.

Changed in version 2.6: The attribute supports dot notation for nested access.

jinja-filters.indent(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _width: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") \= 4_, _first: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _blank: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Return a copy of the string with each line indented by 4 spaces. The first line and blank lines are not indented by default.

Parameters:

-   **width** – Number of spaces, or a string, to indent by.
    
-   **first** – Don’t skip indenting the first line.
    
-   **blank** – Don’t skip indenting empty lines.
    

Changelog

Changed in version 3.0: `width` can be a string.

Changed in version 2.10: Blank lines are not indented by default.

Rename the `indentfirst` argument to `first`.

jinja-filters.int(_value: Any_, _default: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") \= 0_, _base: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") \= 10_) → [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")

Convert the value into an integer. If the conversion doesn’t work it will return `0`. You can override this default using the first parameter. You can also override the default base (10) in the second parameter, which handles input with prefixes such as 0b, 0o and 0x for bases 2, 8 and 16 respectively. The base is ignored for decimal numbers and non-string values.

jinja-filters.items(_value: Mapping\[K, V\] | [jinja2.runtime.Undefined](https://jinja.palletsprojects.com/en/latest/api/#jinja2.Undefined "jinja2.runtime.Undefined")_) → Iterator\[[Tuple](https://jinja.palletsprojects.com/en/latest/extensions/#jinja2.nodes.Tuple "jinja2.nodes.Tuple")\[K, V\]\]

Return an iterator over the `(key, value)` items of a mapping.

`x|items` is the same as `x.items()`, except if `x` is undefined an empty iterator is returned.

This filter is useful if you expect the template to be rendered with an implementation of Jinja in another programming language that does not have a `.items()` method on its mapping type.

```
<dl>
{% for key, value in my_dict|items %}
    <dt>{{ key }}
    <dd>{{ value }}
{% endfor %}
</dl>
```

Changelog

Added in version 3.1.

jinja-filters.join(_value: Iterable\[Any\]_, _d: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") \= ''_, _attribute: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | NoneType \= None_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Return a string which is the concatenation of the strings in the sequence. The separator between elements is an empty string per default, you can define it with the optional parameter:

```
{{ [1, 2, 3]|join('|') }}
    -> 1|2|3

{{ [1, 2, 3]|join }}
    -> 123
```

It is also possible to join certain attributes of an object:

```
{{ users|join(', ', attribute='username') }}
```

Changelog

Added in version 2.6: The `attribute` parameter was added.

jinja-filters.last(_seq: 't.Reversible\[V\]'_) → 't.Union\[V, Undefined\]'

Return the last item of a sequence.

Note: Does not work with generators. You may want to explicitly convert it to a list:

```
{{ data | selectattr('name', '==', 'Jinja') | list | last }}
```

jinja-filters.length(_obj_, _/_)

Return the number of items in a container.

Aliases:

`count`

jinja-filters.list(_value: 't.Iterable\[V\]'_) → 't.List\[V\]'

Convert the value into a list. If it was a string the returned list will be a list of characters.

jinja-filters.lower(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Convert a value to lowercase.

jinja-filters.map(_value: Iterable\[Any\]_, _\*args: Any_, _\*\*kwargs: Any_) → Iterable\[Any\]

Applies a filter on a sequence of objects or looks up an attribute. This is useful when dealing with lists of objects but you are really only interested in a certain value of it.

The basic usage is mapping on an attribute. Imagine you have a list of users but you are only interested in a list of usernames:

```
Users on this page: {{ users|map(attribute='username')|join(', ') }}
```

You can specify a `default` value to use if an object in the list does not have the given attribute.

```
{{ users|map(attribute="username", default="Anonymous")|join(", ") }}
```

Alternatively you can let it invoke a filter by passing the name of the filter and the arguments afterwards. A good example would be applying a text conversion filter on a sequence:

```
Users on this page: {{ titles|map('lower')|join(', ') }}
```

Similar to a generator comprehension such as:

```
(u.username for u in users)
(getattr(u, "username", "Anonymous") for u in users)
(do_lower(x) for x in titles)
```

Changelog

Changed in version 2.11.0: Added the `default` parameter.

Added in version 2.7.

jinja-filters.max(_value: 't.Iterable\[V\]'_, _case\_sensitive: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _attribute: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | NoneType \= None_) → 't.Union\[V, Undefined\]'

Return the largest item from the sequence.

```jinja
{{ [1, 2, 3]|max }}
    -> 3
```

Parameters:

-   **case\_sensitive** – Treat upper and lower case strings as distinct.
    
-   **attribute** – Get the object with the max value of this attribute.
    

jinja-filters.min(_value: 't.Iterable\[V\]'_, _case\_sensitive: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _attribute: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | NoneType \= None_) → 't.Union\[V, Undefined\]'

Return the smallest item from the sequence.

```
{{ [1, 2, 3]|min }}
    -> 1
```

Parameters:

-   **case\_sensitive** – Treat upper and lower case strings as distinct.
    
-   **attribute** – Get the object with the min value of this attribute.
    

jinja-filters.pprint(_value: Any_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Pretty print a variable. Useful for debugging.

jinja-filters.random(_seq: 't.Sequence\[V\]'_) → 't.Union\[V, Undefined\]'

Return a random item from the sequence.

jinja-filters.reject(_value: 't.Iterable\[V\]'_, _\*args: Any_, _\*\*kwargs: Any_) → 't.Iterator\[V\]'

Filters a sequence of objects by applying a test to each object, and rejecting the objects with the test succeeding.

If no test is specified, each object will be evaluated as a boolean.

Example usage:

```
{{ numbers|reject("odd") }}
```

Similar to a generator comprehension such as:

```
(n for n in numbers if not test_odd(n))
```

Changelog

Added in version 2.7.

jinja-filters.rejectattr(_value: 't.Iterable\[V\]'_, _\*args: Any_, _\*\*kwargs: Any_) → 't.Iterator\[V\]'

Filters a sequence of objects by applying a test to the specified attribute of each object, and rejecting the objects with the test succeeding.

If no test is specified, the attribute’s value will be evaluated as a boolean.

```
{{ users|rejectattr("is_active") }}
{{ users|rejectattr("email", "none") }}
```

Similar to a generator comprehension such as:

```
(u for user in users if not user.is_active)
(u for user in users if not test_none(user.email))
```

Changelog

Added in version 2.7.

jinja-filters.replace(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _old: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _new: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _count: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Return a copy of the value with all occurrences of a substring replaced with a new one. The first argument is the substring that should be replaced, the second is the replacement string. If the optional third argument `count` is given, only the first `count` occurrences are replaced:

```
{{ "Hello World"|replace("Hello", "Goodbye") }}
    -> Goodbye World

{{ "aaaaargh"|replace("a", "d'oh, ", 2) }}
    -> d'oh, d'oh, aaargh
```

jinja-filters.reverse(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | Iterable\[V\]_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | Iterable\[V\]

Reverse the object or return an iterator that iterates over it the other way round.

jinja-filters.round(_value: [float](https://docs.python.org/3/library/functions.html#float "(in Python v3.12)")_, _precision: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") \= 0_, _method: 'te.Literal\["common", "ceil", "floor"\]' \= 'common'_) → [float](https://docs.python.org/3/library/functions.html#float "(in Python v3.12)")

Round the number to a given precision. The first parameter specifies the precision (default is `0`), the second the rounding method:

-   `'common'` rounds either up or down
    
-   `'ceil'` always rounds up
    
-   `'floor'` always rounds down
    

If you don’t specify a method `'common'` is used.

```
{{ 42.55|round }}
    -> 43.0
{{ 42.55|round(1, 'floor') }}
    -> 42.5
```

Note that even if rounded to 0 precision, a float is returned. If you need a real integer, pipe it through `int`:

```
{{ 42.55|round|int }}
    -> 43
```

jinja-filters.safe(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → markupsafe.Markup

Mark the value as safe which means that in an environment with automatic escaping enabled this variable will not be escaped.

jinja-filters.select(_value: 't.Iterable\[V\]'_, _\*args: Any_, _\*\*kwargs: Any_) → 't.Iterator\[V\]'

Filters a sequence of objects by applying a test to each object, and only selecting the objects with the test succeeding.

If no test is specified, each object will be evaluated as a boolean.

Example usage:

```
{{ numbers|select("odd") }}
{{ numbers|select("odd") }}
{{ numbers|select("divisibleby", 3) }}
{{ numbers|select("lessthan", 42) }}
{{ strings|select("equalto", "mystring") }}
```

Similar to a generator comprehension such as:

```
(n for n in numbers if test_odd(n))
(n for n in numbers if test_divisibleby(n, 3))
```

Changelog

Added in version 2.7.

jinja-filters.selectattr(_value: 't.Iterable\[V\]'_, _\*args: Any_, _\*\*kwargs: Any_) → 't.Iterator\[V\]'

Filters a sequence of objects by applying a test to the specified attribute of each object, and only selecting the objects with the test succeeding.

If no test is specified, the attribute’s value will be evaluated as a boolean.

Example usage:

```
{{ users|selectattr("is_active") }}
{{ users|selectattr("email", "none") }}
```

Similar to a generator comprehension such as:

```
(u for user in users if user.is_active)
(u for user in users if test_none(user.email))
```

Changelog

Added in version 2.7.

jinja-filters.slice(_value: 't.Collection\[V\]'_, _slices: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_, _fill\_with: 't.Optional\[V\]' \= None_) → 't.Iterator\[t.List\[V\]\]'

Slice an iterator and return a list of lists containing those items. Useful if you want to create a div containing three ul tags that represent columns:

```
<div class="columnwrapper">
  {%- for column in items|slice(3) %}
    <ul class="column-{{ loop.index }}">
    {%- for item in column %}
      <li>{{ item }}</li>
    {%- endfor %}
    </ul>
  {%- endfor %}
</div>
```

If you pass it a second argument it’s used to fill missing values on the last iteration.

jinja-filters.sort(_value: 't.Iterable\[V\]'_, _reverse: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _case\_sensitive: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _attribute: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | NoneType \= None_) → 't.List\[V\]'

Sort an iterable using Python’s [`sorted()`](https://docs.python.org/3/library/functions.html#sorted "(in Python v3.12)").

```
{% for city in cities|sort %}
    ...
{% endfor %}
```

Parameters:

-   **reverse** – Sort descending instead of ascending.
    
-   **case\_sensitive** – When sorting strings, sort upper and lower case separately.
    
-   **attribute** – When sorting objects or dicts, an attribute or key to sort by. Can use dot notation like `"address.city"`. Can be a list of attributes like `"age,name"`.
    

The sort is stable, it does not change the relative order of elements that compare equal. This makes it is possible to chain sorts on different attributes and ordering.

```
{% for user in users|sort(attribute="name")
    |sort(reverse=true, attribute="age") %}
    ...
{% endfor %}
```

As a shortcut to chaining when the direction is the same for all attributes, pass a comma separate list of attributes.

```
{% for user in users|sort(attribute="age,name") %}
    ...
{% endfor %}
```

Changelog

Changed in version 2.11.0: The `attribute` parameter can be a comma separated list of attributes, e.g. `"age,name"`.

Changed in version 2.6: The `attribute` parameter was added.

jinja-filters.string(_value_)

Convert an object to a string if it isn’t already. This preserves a `Markup` string rather than converting it back to a basic string, so it will still be marked as safe and won’t be escaped again.

```output
>>> value = escape("<User 1>")
>>> value
Markup('&lt;User 1&gt;')
>>> escape(str(value))
Markup('&amp;lt;User 1&amp;gt;')
>>> escape(soft_str(value))
Markup('&lt;User 1&gt;')
```

jinja-filters.striptags(_value: 't.Union\[str, HasHTML\]'_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Strip SGML/XML tags and replace adjacent whitespace by one space.

jinja-filters.sum(_iterable: 't.Iterable\[V\]'_, _attribute: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | NoneType \= None_, _start: V \= 0_) → V

Returns the sum of a sequence of numbers plus the value of parameter ‘start’ (which defaults to 0). When the sequence is empty it returns start.

It is also possible to sum up only certain attributes:

```
Total: {{ items|sum(attribute='price') }}
```

Changelog

Changed in version 2.6: The `attribute` parameter was added to allow summing up over attributes. Also the `start` parameter was moved on to the right.

jinja-filters.title(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Return a titlecased version of the value. I.e. words will start with uppercase letters, all remaining characters are lowercase.

jinja-filters.tojson(_value: Any_, _indent: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_) → markupsafe.Markup

Serialize an object to a string of JSON, and mark it safe to render in HTML. This filter is only for use in HTML documents.

The returned string is safe to render in HTML documents and `<script>` tags. The exception is in HTML attributes that are double quoted; either use single quotes or the `|forceescape` filter.

Parameters:

-   **value** – The object to serialize to JSON.
    
-   **indent** – The `indent` parameter passed to `dumps`, for pretty-printing the value.
    

Changelog

Added in version 2.9.

jinja-filters.trim(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _chars: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Strip leading and trailing characters, by default whitespace.

jinja-filters.truncate(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _length: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") \= 255_, _killwords: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _end: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") \= '...'_, _leeway: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Return a truncated copy of the string. The length is specified with the first parameter which defaults to `255`. If the second parameter is `true` the filter will cut the text at length. Otherwise it will discard the last word. If the text was in fact truncated it will append an ellipsis sign (`"..."`). If you want a different ellipsis sign than `"..."` you can specify it using the third parameter. Strings that only exceed the length by the tolerance margin given in the fourth parameter will not be truncated.

```
{{ "foo bar baz qux"|truncate(9) }}
    -> "foo..."
{{ "foo bar baz qux"|truncate(9, True) }}
    -> "foo ba..."
{{ "foo bar baz qux"|truncate(11) }}
    -> "foo bar baz qux"
{{ "foo bar baz qux"|truncate(11, False, '...', 0) }}
    -> "foo bar..."
```

The default leeway on newer Jinja versions is 5 and was 0 before but can be reconfigured globally.

jinja-filters.unique(_value: 't.Iterable\[V\]'_, _case\_sensitive: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _attribute: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | NoneType \= None_) → 't.Iterator\[V\]'

Returns a list of unique items from the given iterable.

```
{{ ['foo', 'bar', 'foobar', 'FooBar']|unique|list }}
    -> ['foo', 'bar', 'foobar']
```

The unique items are yielded in the same order as their first occurrence in the iterable passed to the filter.

Parameters:

-   **case\_sensitive** – Treat upper and lower case strings as distinct.
    
-   **attribute** – Filter objects with unique values for this attribute.
    

jinja-filters.upper(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Convert a value to uppercase.

jinja-filters.urlencode(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | Mapping\[[str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)"), Any\] | Iterable\[[Tuple](https://jinja.palletsprojects.com/en/latest/extensions/#jinja2.nodes.Tuple "jinja2.nodes.Tuple")\[[str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)"), Any\]\]_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Quote data for use in a URL path or query using UTF-8.

Basic wrapper around [`urllib.parse.quote()`](https://docs.python.org/3/library/urllib.parse.html#urllib.parse.quote "(in Python v3.12)") when given a string, or [`urllib.parse.urlencode()`](https://docs.python.org/3/library/urllib.parse.html#urllib.parse.urlencode "(in Python v3.12)") for a dict or iterable.

Parameters:

**value** – Data to quote. A string will be quoted directly. A dict or iterable of `(key, value)` pairs will be joined as a query string.

When given a string, “/” is not quoted. HTTP servers treat “/” and “%2F” equivalently in paths. If you need quoted slashes, use the `|replace("/", "%2F")` filter.

Changelog

Added in version 2.7.

jinja-filters.urlize(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _trim\_url\_limit: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_, _nofollow: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= False_, _target: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_, _rel: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_, _extra\_schemes: Iterable\[[str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")\] | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Convert URLs in text into clickable links.

This may not recognize links in some situations. Usually, a more comprehensive formatter, such as a Markdown library, is a better choice.

Works on `http://`, `https://`, `www.`, `mailto:`, and email addresses. Links with trailing punctuation (periods, commas, closing parentheses) and leading punctuation (opening parentheses) are recognized excluding the punctuation. Email addresses that include header fields are not recognized (for example, `mailto:address@example.com?cc=copy@example.com`).

Parameters:

-   **value** – Original text containing URLs to link.
    
-   **trim\_url\_limit** – Shorten displayed URL values to this length.
    
-   **nofollow** – Add the `rel=nofollow` attribute to links.
    
-   **target** – Add the `target` attribute to links.
    
-   **rel** – Add the `rel` attribute to links.
    
-   **extra\_schemes** – Recognize URLs that start with these schemes in addition to the default behavior. Defaults to `env.policies["urlize.extra_schemes"]`, which defaults to no extra schemes.
    

Changelog

Changed in version 3.0: The `extra_schemes` parameter was added.

Changed in version 3.0: Generate `https://` links for URLs without a scheme.

Changed in version 3.0: The parsing rules were updated. Recognize email addresses with or without the `mailto:` scheme. Validate IP addresses. Ignore parentheses and brackets in more cases.

Changed in version 2.8: The `target` parameter was added.

jinja-filters.wordcount(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")

Count the words in that string.

jinja-filters.wordwrap(_s: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_, _width: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)") \= 79_, _break\_long\_words: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= True_, _wrapstring: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)") | [None](https://docs.python.org/3/library/constants.html#None "(in Python v3.12)") \= None_, _break\_on\_hyphens: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= True_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Wrap a string to the given width. Existing newlines are treated as paragraphs to be wrapped separately.

Parameters:

-   **s** – Original text to wrap.
    
-   **width** – Maximum length of wrapped lines.
    
-   **break\_long\_words** – If a word is longer than `width`, break it across lines.
    
-   **break\_on\_hyphens** – If a word contains hyphens, it may be split across lines.
    
-   **wrapstring** – String to join each wrapped line. Defaults to `Environment.newline_sequence`.
    

Changelog

Changed in version 2.11: Existing newlines are treated as paragraphs wrapped separately.

Changed in version 2.11: Added the `break_on_hyphens` parameter.

Changed in version 2.7: Added the `wrapstring` parameter.

jinja-filters.xmlattr(_d: Mapping\[[str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)"), Any\]_, _autospace: [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)") \= True_) → [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")

Create an SGML/XML attribute string based on the items in a dict.

**Values** that are neither `none` nor `undefined` are automatically escaped, safely allowing untrusted user input.

User input should not be used as **keys** to this filter. If any key contains a space, `/` solidus, `>` greater-than sign, or `=` equals sign, this fails with a `ValueError`. Regardless of this, user input should never be used as keys to this filter, or must be separately validated first.

```
<ul{{ {'class': 'my_list', 'missing': none,
        'id': 'list-%d'|format(variable)}|xmlattr }}>
...
</ul>
```

Results in something like this:

```
<ul class="my_list" id="list-42">
...
</ul>
```

As you can see it automatically prepends a space in front of the item if the filter returned something unless the second parameter is false.

Changelog

Changed in version 3.1.4: Keys with `/` solidus, `>` greater-than sign, or `=` equals sign are not allowed.

Changed in version 3.1.3: Keys with spaces are not allowed.

## List of Builtin Tests

jinja-tests.boolean(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the object is a boolean value.

Changelog

Added in version 2.11.

jinja-tests.callable(_obj_, _/_)

Return whether the object is callable (i.e., some kind of function).

Note that classes are callable, as are instances of classes with a \_\_call\_\_() method.

jinja-tests.defined(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is defined:

```
{% if variable is defined %}
    value of variable: {{ variable }}
{% else %}
    variable is not defined
{% endif %}
```

See the `default()` filter for a simple way to set undefined variables.

jinja-tests.divisibleby(_value: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_, _num: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Check if a variable is divisible by a number.

jinja-tests.eq(_a_, _b_, _/_)

Same as a == b.

Aliases:

`==`, `equalto`

jinja-tests.escaped(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Check if the value is escaped.

jinja-tests.even(_value: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is even.

jinja-tests.false(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the object is False.

Changelog

Added in version 2.11.

jinja-tests.filter(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Check if a filter exists by name. Useful if a filter may be optionally available.

```
{% if 'markdown' is filter %}
    {{ value | markdown }}
{% else %}
    {{ value }}
{% endif %}
```

Changelog

Added in version 3.0.

jinja-tests.float(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the object is a float.

Changelog

Added in version 2.11.

jinja-tests.ge(_a_, _b_, _/_)

Same as a >= b.

Aliases:

`>=`

jinja-tests.gt(_a_, _b_, _/_)

Same as a > b.

Aliases:

`>`, `greaterthan`

jinja-tests.in(_value: Any_, _seq: Container\[Any\]_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Check if value is in seq.

Changelog

Added in version 2.10.

jinja-tests.integer(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the object is an integer.

Changelog

Added in version 2.11.

jinja-tests.iterable(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Check if it’s possible to iterate over an object.

jinja-tests.le(_a_, _b_, _/_)

Same as a <= b.

Aliases:

`<=`

jinja-tests.lower(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is lowercased.

jinja-tests.lt(_a_, _b_, _/_)

Same as a < b.

Aliases:

`<`, `lessthan`

jinja-tests.mapping(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the object is a mapping (dict etc.).

Changelog

Added in version 2.6.

jinja-tests.ne(_a_, _b_, _/_)

Same as a != b.

Aliases:

`!=`

jinja-tests.none(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is none.

jinja-tests.number(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is a number.

jinja-tests.odd(_value: [int](https://docs.python.org/3/library/functions.html#int "(in Python v3.12)")_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is odd.

jinja-tests.sameas(_value: Any_, _other: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Check if an object points to the same memory address than another object:

```
{% if foo.attribute is sameas false %}
    the foo attribute really is the `False` singleton
{% endif %}
```

jinja-tests.sequence(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is a sequence. Sequences are variables that are iterable.

jinja-tests.string(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the object is a string.

jinja-tests.test(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Check if a test exists by name. Useful if a test may be optionally available.

```
{% if 'loud' is test %}
    {% if value is loud %}
        {{ value|upper }}
    {% else %}
        {{ value|lower }}
    {% endif %}
{% else %}
    {{ value }}
{% endif %}
```

Changelog

Added in version 3.0.

jinja-tests.true(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the object is True.

Changelog

Added in version 2.11.

jinja-tests.undefined(_value: Any_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Like [`defined()`](https://jinja.palletsprojects.com/en/latest/templates/#jinja-tests.defined "jinja-tests.defined") but the other way round.

jinja-tests.upper(_value: [str](https://docs.python.org/3/library/stdtypes.html#str "(in Python v3.12)")_) → [bool](https://docs.python.org/3/library/functions.html#bool "(in Python v3.12)")

Return true if the variable is uppercased.

## List of Global Functions

The following functions are available in the global scope by default:

jinja-globals.range(\[_start_, \]_stop_\[, _step_\])

Return a list containing an arithmetic progression of integers. `range(i, j)` returns `[i, i+1, i+2, ..., j-1]`; start (!) defaults to `0`. When step is given, it specifies the increment (or decrement). For example, `range(4)` and `range(0, 4, 1)` return `[0, 1, 2, 3]`. The end point is omitted! These are exactly the valid indices for a list of 4 elements.

This is useful to repeat a template block multiple times, e.g. to fill a list. Imagine you have 7 users in the list but you want to render three empty items to enforce a height with CSS:

```
<ul>
{% for user in users %}
    <li>{{ user.username }}</li>
{% endfor %}
{% for number in range(10 - users|count) %}
    <li class="empty"><span>...</span></li>
{% endfor %}
</ul>
```

jinja-globals.lipsum(_n\=5_, _html\=True_, _min\=20_, _max\=100_)

Generates some lorem ipsum for the template. By default, five paragraphs of HTML are generated with each paragraph between 20 and 100 words. If html is False, regular text is returned. This is useful to generate simple contents for layout testing.

jinja-globals.dict(_\\\*\*items_)

A convenient alternative to dict literals. `{'foo': 'bar'}` is the same as `dict(foo='bar')`.

_class_ jinja-globals.cycler(_\\\*items_)

Cycle through values by yielding them one at a time, then restarting once the end is reached.

Similar to `loop.cycle`, but can be used outside loops or across multiple loops. For example, render a list of folders and files in a list, alternating giving them “odd” and “even” classes.

```
{% set row_class = cycler("odd", "even") %}
<ul class="browser">
{% for folder in folders %}
  <li class="folder {{ row_class.next() }}">{{ folder }}
{% endfor %}
{% for file in files %}
  <li class="file {{ row_class.next() }}">{{ file }}
{% endfor %}
</ul>
```

Parameters:

**items** – Each positional argument will be yielded in the order given for each cycle.

Changelog

Added in version 2.1.

_property_ current

Return the current item. Equivalent to the item that will be returned next time [`next()`](https://jinja.palletsprojects.com/en/latest/templates/#jinja-globals.cycler.next "jinja-globals.cycler.next") is called.

next()

Return the current item, then advance [`current`](https://jinja.palletsprojects.com/en/latest/templates/#jinja-globals.cycler.current "jinja-globals.cycler.current") to the next item.

reset()

Resets the current item to the first item.

_class_ jinja-globals.joiner(_sep\=', '_)

A tiny helper that can be used to “join” multiple sections. A joiner is passed a string and will return that string every time it’s called, except the first time (in which case it returns an empty string). You can use this to join things:

```
{% set pipe = joiner("|") %}
{% if categories %} {{ pipe() }}
    Categories: {{ categories|join(", ") }}
{% endif %}
{% if author %} {{ pipe() }}
    Author: {{ author() }}
{% endif %}
{% if can_edit %} {{ pipe() }}
    <a href="?action=edit">Edit</a>
{% endif %}
```

Changelog

Added in version 2.1.

_class_ jinja-globals.namespace(_..._)

Creates a new container that allows attribute assignment using the `{% set %}` tag:

```
{% set ns = namespace() %}
{% set ns.foo = 'bar' %}
```

The main purpose of this is to allow carrying a value from within a loop body to an outer scope. Initial values can be provided as a dict, as keyword arguments, or both (same behavior as Python’s `dict` constructor):

```
{% set ns = namespace(found=false) %}
{% for item in items %}
    {% if item.check_something() %}
        {% set ns.found = true %}
    {% endif %}
    * {{ item.title }}
{% endfor %}
Found item having something: {{ ns.found }}
```

Changelog

Added in version 2.10.

## Extensions

The following sections cover the built-in Jinja extensions that may be enabled by an application. An application could also provide further extensions not covered by this documentation; in which case there should be a separate document explaining said [extensions](https://jinja.palletsprojects.com/en/latest/extensions/#jinja-extensions).

### i18n

If the [i18n Extension](https://jinja.palletsprojects.com/en/latest/extensions/#i18n-extension) is enabled, it’s possible to mark text in the template as translatable. To mark a section as translatable, use a `trans` block:

```
{% trans %}Hello, {{ user }}!{% endtrans %}
```

Inside the block, no statements are allowed, only text and simple variable tags.

Variable tags can only be a name, not attribute access, filters, or other expressions. To use an expression, bind it to a name in the `trans` tag for use in the block.

```
{% trans user=user.username %}Hello, {{ user }}!{% endtrans %}
```

To bind more than one expression, separate each with a comma (`,`).

```
{% trans book_title=book.title, author=author.name %}
This is {{ book_title }} by {{ author }}
{% endtrans %}
```

To pluralize, specify both the singular and plural forms separated by the `pluralize` tag.

```
{% trans count=list|length %}
There is {{ count }} {{ name }} object.
{% pluralize %}
There are {{ count }} {{ name }} objects.
{% endtrans %}
```

By default, the first variable in a block is used to determine whether to use singular or plural form. If that isn’t correct, specify the variable used for pluralizing as a parameter to `pluralize`.

```
{% trans ..., user_count=users|length %}...
{% pluralize user_count %}...{% endtrans %}
```

When translating blocks of text, whitespace and linebreaks result in hard to read and error-prone translation strings. To avoid this, a trans block can be marked as trimmed, which will replace all linebreaks and the whitespace surrounding them with a single space and remove leading and trailing whitespace.

```
{% trans trimmed book_title=book.title %}
    This is {{ book_title }}.
    You should read it!
{% endtrans %}
```

This results in `This is %(book_title)s. You should read it!` in the translation file.

If trimming is enabled globally, the `notrimmed` modifier can be used to disable it for a block.

Changelog

Added in version 2.10: The `trimmed` and `notrimmed` modifiers have been added.

If the translation depends on the context that the message appears in, the `pgettext` and `npgettext` functions take a `context` string as the first argument, which is used to select the appropriate translation. To specify a context with the `{% trans %}` tag, provide a string as the first token after `trans`.

```
{% trans "fruit" %}apple{% endtrans %}
{% trans "fruit" trimmed count -%}
    1 apple
{%- pluralize -%}
    {{ count }} apples
{%- endtrans %}
```

Changelog

Added in version 3.1: A context can be passed to the `trans` tag to use `pgettext` and `npgettext`.

It’s possible to translate strings in expressions with these functions:

-   `_(message)`: Alias for `gettext`.
    
-   `gettext(message)`: Translate a message.
    
-   `ngettext(singluar, plural, n)`: Translate a singular or plural message based on a count variable.
    
-   `pgettext(context, message)`: Like `gettext()`, but picks the translation based on the context string.
    
-   `npgettext(context, singular, plural, n)`: Like `npgettext()`, but picks the translation based on the context string.
    

You can print a translated string like this:

```
{{ _("Hello, World!") }}
```

To use placeholders, use the `format` filter.

```
{{ _("Hello, %(user)s!")|format(user=user.username) }}
```

Always use keyword arguments to `format`, as other languages may not use the words in the same order.

If [New Style Gettext](https://jinja.palletsprojects.com/en/latest/extensions/#newstyle-gettext) calls are activated, using placeholders is easier. Formatting is part of the `gettext` call instead of using the `format` filter.

```
{{ gettext('Hello World!') }}
{{ gettext('Hello %(name)s!', name='World') }}
{{ ngettext('%(num)d apple', '%(num)d apples', apples|count) }}
```

The `ngettext` function’s format string automatically receives the count as a `num` parameter in addition to the given parameters.

### Expression Statement

If the expression-statement extension is loaded, a tag called `do` is available that works exactly like the regular variable expression (`{{ ... }}`); except it doesn’t print anything. This can be used to modify lists:

```
{% do navigation.append('a string') %}
```

### Loop Controls

If the application enables the [Loop Controls](https://jinja.palletsprojects.com/en/latest/extensions/#loopcontrols-extension), it’s possible to use `break` and `continue` in loops. When `break` is reached, the loop is terminated; if `continue` is reached, the processing is stopped and continues with the next iteration.

Here’s a loop that skips every second item:

```
{% for user in users %}
    {%- if loop.index is even %}{% continue %}{% endif %}
    ...
{% endfor %}
```

Likewise, a loop that stops processing after the 10th iteration:

```
{% for user in users %}
    {%- if loop.index >= 10 %}{% break %}{% endif %}
{%- endfor %}
```

Note that `loop.index` starts with 1, and `loop.index0` starts with 0 (See: [For](https://jinja.palletsprojects.com/en/latest/templates/#for-loop)).

### Debug Statement

If the [Debug Extension](https://jinja.palletsprojects.com/en/latest/extensions/#debug-extension) is enabled, a `{% debug %}` tag will be available to dump the current context as well as the available filters and tests. This is useful to see what’s available to use in the template without setting up a debugger.

```
<pre>{% debug %}</pre>
```

```
{'context': {'cycler': <class 'jinja2.utils.Cycler'>,
             ...,
             'namespace': <class 'jinja2.utils.Namespace'>},
 'filters': ['abs', 'attr', 'batch', 'capitalize', 'center', 'count', 'd',
             ..., 'urlencode', 'urlize', 'wordcount', 'wordwrap', 'xmlattr'],
 'tests': ['!=', '<', '<=', '==', '>', '>=', 'callable', 'defined',
           ..., 'odd', 'sameas', 'sequence', 'string', 'undefined', 'upper']}
```

### With Statement

Changelog

Added in version 2.3.

The with statement makes it possible to create a new inner scope. Variables set within this scope are not visible outside of the scope.

With in a nutshell:

```
{% with %}
    {% set foo = 42 %}
    {{ foo }}           foo is 42 here
{% endwith %}
foo is not visible here any longer
```

Because it is common to set variables at the beginning of the scope, you can do that within the `with` statement. The following two examples are equivalent:

```
{% with foo = 42 %}
    {{ foo }}
{% endwith %}

{% with %}
    {% set foo = 42 %}
    {{ foo }}
{% endwith %}
```

An important note on scoping here. In Jinja versions before 2.9 the behavior of referencing one variable to another had some unintended consequences. In particular one variable could refer to another defined in the same with block’s opening statement. This caused issues with the cleaned up scoping behavior and has since been improved. In particular in newer Jinja versions the following code always refers to the variable `a` from outside the `with` block:

```
{% with a={}, b=a.attribute %}...{% endwith %}
```

In earlier Jinja versions the `b` attribute would refer to the results of the first attribute. If you depend on this behavior you can rewrite it to use the `set` tag:

```
{% with a={} %}
    {% set b = a.attribute %}
{% endwith %}
```

Extension

In older versions of Jinja (before 2.9) it was required to enable this feature with an extension. It’s now enabled by default.

## Autoescape Overrides

Changelog

Added in version 2.4.

If you want you can activate and deactivate the autoescaping from within the templates.

Example:

```
{% autoescape true %}
    Autoescaping is active within this block
{% endautoescape %}

{% autoescape false %}
    Autoescaping is inactive within this block
{% endautoescape %}
```

After an `endautoescape` the behavior is reverted to what it was before.

Extension

In older versions of Jinja (before 2.9) it was required to enable this feature with an extension. It’s now enabled by default.

## Reference

- https://jinja.palletsprojects.com/en/latest/templates/
