""" Factory classes for users"""

from factory import Faker, Sequence
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText

from users.models import User


class UserFactory(DjangoModelFactory):
    """Factory for User"""

    username = Sequence(lambda n: "user_%d" % n)
    email = FuzzyText(suffix="@example.com")
    name = Faker("name")
    is_active = True

    class Meta:
        model = User
