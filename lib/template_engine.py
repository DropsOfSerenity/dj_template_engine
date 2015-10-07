"""A Simple implementation of a template engine based on django's
implementation. Builds a python expression to evaluate and get the globals back
from"""

import re
from .exceptions import TemplateSyntaxError


class Template(object):
    """Has the responbility of constructing context, and rendering templates"""

    def __init__(self, template, *contexts):
        """Construct a Template with the given `template` text

        `contexts` are dictionaries of values to use for future renderings.
        """
        self.context = {}
        for context in contexts:
            self.context.update(context)

        self.all_vars = set()
        self.loop_vars = set()

        code = CodeBuilder()
        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered = []

        def flush_output():
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []
        tokens = self._tokenize(template)
        for token in tokens:
            if token.startswith('{#'):
                continue
            elif token.startswith('{{'):
                # an expression to evaluate.
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str(%s)" % expr)
            elif token.startswith('{%'):
                # action tag: split into words to parse further
                flush_output()
                words = token[2:-2].strip().split()

                if words[0] == 'if':
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if %s:" % self._expr_code(words[1]))
                    code.indent()
                elif words[0] == 'for':
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                        "for c_%s in %s:" % (
                            words[1],
                            self._expr_code(words[3])
                        )
                    )
                    code.indent()
                elif words[0].startswith('end'):
                    # pop the stack
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                if token:
                    buffered.append(repr(token))
        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

        code.add_line("return ''.join(result)")
        code.dedent()

        self._render_function = code.get_globals()['render_function']

    def render(self, context=None):
        """Render the template by applying `context`"""
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)

    def _tokenize(self, template):
        """Split the template into raw text tokens and actionable tokens."""
        return re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", template)

    def _do_dots(self, var, *dots):
        """Evaluate dotted expression at runtime."""
        value = var
        try:
            for dot in dots:
                try:
                    value = value[dot]  # dictionary lookup
                except (TypeError, AttributeError, KeyError, ValueError,
                        IndexError):
                    value = getattr(value, dot)
                if callable(value):
                    value = value()
        except Exception:
            print "Something went wrong while looking up variable '%s'" % var
            value = ""  # silent

        return value

    def _variable(self, name, vars_set):
        """Track `name` is used as a variable.

        Adds the name to `vars_set` which would be a set of variable names.

        Raises: TemplateSyntaxError if `name` is not a valid python var."""
        if not re.match(r"", name):
            self._syntax_error("Not a valid variable name", name)
        vars_set.add(name)

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        if "|" in expr:
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        elif "." in expr:
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" % (code, args)
        else:
            self._variable(expr, self.all_vars)
            code = "c_%s" % expr
        return code

    def _syntax_error(self, msg, thing):
        """Raise syntax error given the message and thing."""
        raise TemplateSyntaxError("%s: %r" % (msg, thing))


class CodeBuilder(object):
    """Build source code"""

    INDENT_STEP = 4

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent

    def add_line(self, line):
        """Adds a line of source to the code. Provides indentation and
        newline"""
        self.code.extend([" " * self.indent_level, line, "\n"])

    def indent(self):
        """Increase the indent for the following lines."""
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        """Decrease the indent for the following lines."""
        self.indent_level -= self.INDENT_STEP

    def add_section(self):
        """Adds a section, a sub-CodeBuilder"""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        """Execute the code, and return a dict of the globals it defines."""
        assert self.indent_level == 0

        python_source = str(self)
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace
