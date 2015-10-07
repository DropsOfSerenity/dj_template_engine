"""Tests for TemplateEngine"""

from unittest import TestCase
from template_engine import Template, TemplateSyntaxError


class ClassWithAttributes(object):
    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)


class TemplateTest(TestCase):
    def try_render(self, text, ctx=None, result=None):
        actual = Template(text).render(ctx or {})
        if result:
            self.assertEqual(actual, result)

    def test_identity(self):
        self.assertEqual(Template("yolo").render(), "yolo")

    def test_variables(self):
        self.try_render("Yolo, {{ name }} !", {"name": "Bob"}, "Yolo, Bob !")

    def test_undefined_varaibles(self):
        with self.assertRaises(KeyError):
            self.try_render("Hi {{ name }}")

    def test_pipes(self):
        data = {
            "name": "bob",
            "upper": lambda x: x.upper(),
            "first": lambda x: x[0]
        }
        self.try_render("Hello, {{ name|upper }}", data, "Hello, BOB")
        self.try_render("Hello, {{ name|upper|first }}", data, "Hello, B")

    def test_reusability(self):
        global_vars = {
            "upper": lambda x: x.upper(),
            "punct": "!"
        }
        t = Template("This is {{ name|upper }}{{punct}}", global_vars)
        self.assertEqual(t.render({"name": "bob"}), "This is BOB!")
        self.assertEqual(t.render({"name": "jim"}), "This is JIM!")

    def test_attributes_on_objects(self):
        obj = ClassWithAttributes(a="yolo")
        self.try_render("{{ obj.a }}", locals(), "yolo")

        obj2 = ClassWithAttributes(obj=obj, b="swag")
        self.try_render("{{ obj2.obj.a }} {{ obj2.b }}", locals(), "yolo swag")

    def test_class_methods_are_called(self):
        class ClassWithMethod(ClassWithAttributes):
            def return_stuff(self):
                return self.stuff + " = " + self.stuff

        obj = ClassWithMethod(stuff="yoloswag")
        self.try_render("{{ obj.return_stuff }}", locals(),
                        "yoloswag = yoloswag")

    def test_dict_lookup_works(self):
        dic = {"yolo": 1, "swag": 2}
        self.try_render("{{dic.yolo}} {{dic.swag}}", locals(), "1 2")

    def test_for_loops(self):
        numbers = [1, 2, 3, 4]
        self.try_render(
            "{% for num in numbers %}{{ num }}, {% endfor %}I can count.",
            locals(),
            "1, 2, 3, 4, I can count."
        )

    def test_empty_loop_var(self):
        self.try_render(
            "{% for num in nums %}{{ num }}{% endfor %}",
            {'nums': []},
            ""
        )

    def test_comments(self):
        self.try_render(
            "{# Something that shouldn't display #}",
            {},
            ""
        )

        self.try_render(
            "Price: {# here is the price #}{{ price }}",
            {'price': 3.33},
            "Price: 3.33"
        )

    def test_if(self):
        self.try_render(
            "{% if conditional %}Display Me!{% endif %}",
            {'conditional': False},
            ""
        )

        self.try_render(
            "{% if conditional %}Display Me!{% endif %}",
            {'conditional': True},
            "Display Me!"
        )

    def test_complex_if(self):
        class ClassWithMethod(ClassWithAttributes):
            def return_stuff(self):
                return self.stuff
        obj = ClassWithMethod(stuff={'cond': "affirmative"})

        self.try_render(
            "{% if obj.return_stuff.cond %}Display Me!{% endif %}",
            locals(),
            "Display Me!"
        )

    def test_unbalanced_tags(self):
        with self.assertRaises(TemplateSyntaxError):
            self.try_render("{% if cond %}")

        with self.assertRaises(TemplateSyntaxError):
            self.try_render("{% for blah in blahs %}")

        with self.assertRaises(TemplateSyntaxError):
            self.try_render("{% if cond %}{% for blah in blahs %}{% endif %}")

    def test_invalid_variable_names(self):
        with self.assertRaises(SyntaxError):
            self.try_render("{{ _@$DSAF }}")
        with self.assertRaises(SyntaxError):
            self.try_render("{% for !! in $$ %}{% endfor %}")

    def test_bad_if(self):
        with self.assertRaises(TemplateSyntaxError):
            self.try_render("{% if %}{% endif %}")

    def test_bad_for(self):
        with self.assertRaises(TemplateSyntaxError):
            self.try_render("{% for %}{% endfor %}")

    def test_invalid_tag(self):
        with self.assertRaises(TemplateSyntaxError):
            self.try_render("{% customtag %}{% endcustomtag %}")
