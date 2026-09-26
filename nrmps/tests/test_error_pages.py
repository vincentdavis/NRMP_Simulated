"""The server-error page renders with no database and no context (plan step 0.7, UX-24).

No test here has database access: pytest-django fails any test that touches the database without the django_db mark,
so these tests prove the 500 page still works when the database is what failed.
"""

from django.template.loader import render_to_string
from django.test import RequestFactory
from django.views.defaults import server_error


def test_500_template_renders_without_context():
    assert "Something went wrong on our side" in render_to_string("500.html")


def test_500_handler_renders_without_database():
    response = server_error(RequestFactory().get("/"))
    assert response.status_code == 500
    assert b"issue tracker" in response.content
