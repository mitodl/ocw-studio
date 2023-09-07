"""Factory classes for users"""

from factory import Faker, SelfAttribute
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText

from users.models import User


class UserFactory(DjangoModelFactory):
    """Factory for User"""

    username = SelfAttribute("email")
    email = FuzzyText(suffix="@example.com")
    name = Faker("name")
    is_active = True

    class Meta:
        model = User
