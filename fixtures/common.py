""" Common fixtures for ocw-studio """
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def drf_client():
    """DRF API anonymous test client"""
    return APIClient()
