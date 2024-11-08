
# Method overloading for different argument type in python

## Challenge

I'm writing a preprocessor in python, part of which works with an AST.

There is a `render()` method that takes care of converting various statements to source code.

Now, I have it like this (shortened):

```python
def render(self, s):
    """ Render a statement by type. """

    # code block (used in structures)
    if isinstance(s, S_Block):
        # delegate to private method that does the work
        return self._render_block(s)

    # empty statement
    if isinstance(s, S_Empty):
        return self._render_empty(s)

    # a function declaration
    if isinstance(s, S_Function):
        return self._render_function(s)

    # ...
```

As you can see, it's tedious, prone to errors and the code is quite long (I have many more kinds of statements).

The ideal solution would be (in Java syntax):

```java
String render(S_Block s)
{
    // render block
}

String render(S_Empty s)
{
    // render empty statement
}

String render(S_Function s)
{
    // render function statement
}

// ...
```

Of course, python can't do this, because it has dynamic typing. When I searched for how to mimick method overloading, all answers just said "You don't want to do that in python". I guess that is true in some cases, but here `kwargs` is really not useful at all.

How would I do this in python, without the hideous kilometre-long sequence if type checking ifs, as shown above? Also, preferably a "pythonic" way to do so?

**Note:** There can be multiple "Renderer" implementations, which render the statements in different manners. I can't therefore move the rendering code to the statements and just call `s.render()`. It must be done in the renderer class.

## Solution 1

The overloading syntax you are looking for can be achieved using [Guido van Rossum's multimethod decorator](http://www.artima.com/weblogs/viewpost.jsp?thread=101605).

Here is a variant of the multimethod decorator which can decorate class methods (the original decorates plain functions). I've named the variant `multidispatch` to disambiguate it from the original:

```python
import functools

def multidispatch(*types):
    def register(function):
        name = function.__name__
        mm = multidispatch.registry.get(name)
        if mm is None:
            @functools.wraps(function)
            def wrapper(self, *args):
                types = tuple(arg.__class__ for arg in args) 
                function = wrapper.typemap.get(types)
                if function is None:
                    raise TypeError("no match")
                return function(self, *args)
            wrapper.typemap = {}
            mm = multidispatch.registry[name] = wrapper
        if types in mm.typemap:
            raise TypeError("duplicate registration")
        mm.typemap[types] = function
        return mm
    return register
multidispatch.registry = {}

```

and it can be used like this:

```python
class Foo(object):
    @multidispatch(str)
    def render(self, s):
        print('string: {}'.format(s))
    @multidispatch(float)
    def render(self, s):
        print('float: {}'.format(s))
    @multidispatch(float, int)
    def render(self, s, t):
        print('float, int: {}, {}'.format(s, t))

foo = Foo()
foo.render('text')
# string: text
foo.render(1.234)
# float: 1.234
foo.render(1.234, 2)
# float, int: 1.234, 2
```

The demo code above shows how to overload the `Foo.render` method based on the types of its arguments.

This code searches for exact matching types as opposed to checking for `isinstance` relationships. It could be modified to handle that (at the expense of making the lookups O(n) instead of O(1)) but since it sounds like you don't need this anyway, I'll leave the code in this simpler form.


## Solution 2

An alternate implementation with [functools.singledispatch](https://docs.python.org/3/library/functools.html#functools.singledispatch), using the decorators as defined in [PEP-443](https://www.python.org/dev/peps/pep-0443/):

```python
from functools import singledispatch

class S_Unknown: pass
class S_Block: pass
class S_Empty: pass
class S_Function: pass
class S_SpecialBlock(S_Block): pass

@singledispatch
def render(s, **kwargs):
  print('Rendering an unknown type')

@render.register(S_Block)
def _(s, **kwargs):
  print('Rendering an S_Block')

@render.register(S_Empty)
def _(s, **kwargs):
  print('Rendering an S_Empty')

@render.register(S_Function)
def _(s, **kwargs):
  print('Rendering an S_Function')

if __name__ == '__main__':
  for t in [S_Unknown, S_Block, S_Empty, S_Function, S_SpecialBlock]:
    print(f'Passing an {t.__name__}')
    render(t())
```

This outputs

```
Passing an S_Unknown
Rendering an unknown type
Passing an S_Block
Rendering an S_Block
Passing an S_Empty
Rendering an S_Empty
Passing an S_Function
Rendering an S_Function
Passing an S_SpecialBlock
Rendering an S_Block
```

I like this version better than the one with the map because it has the same behavior as the implementation that uses `isinstance()`: when you pass an S_SpecialBlock, it passes it to the renderer that takes an S_Block.

### Availability

As mentioned by dano in [another answer](https://stackoverflow.com/a/25344445/3898322), this works in Python 3.4+ and there is a [backport](https://pypi.org/project/singledispatch/) for Python 2.6+.

If you have Python 3.7+, the `register()` attribute supports using type annotations:

```python
@render.register def _(s: S_Block, **kwargs): print('Rendering an S_Block')
```

### Note

The one problem I can see is that you have to pass `s` as a positional argument, which means you can't do `render(s=S_Block())`.

Since `single_dispatch` uses the type of the first argument to figure out which version of `render()` to call, that would result in a TypeError - "render requires at least 1 positional argument" (cf [source code](https://github.com/python/cpython/blob/445f1b35ce8461268438c8a6b327ddc764287e05/Lib/functools.py#L819-L824))

Actually, I think it should be possible to use the keyword argument if there is only one... If you really need that then you can do something similar to [this answer](https://stackoverflow.com/a/24602374/3898322), which creates a custom decorator with a different wrapper. It would be a nice feature of Python as well.

## Reference

- https://stackoverflow.com/questions/25343981/method-overloading-for-different-argument-type-in-python
