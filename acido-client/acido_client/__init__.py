"""
acido-client: REST API client for acido Lambda functions.

This module provides a lightweight client for interacting with acido Lambda functions
via REST API, supporting all operations including fleet, run, ls, rm, and IP management.
"""

__version__ = '0.50.0'

from .client import AcidoClient, AcidoClientError

__all__ = ['AcidoClient', 'AcidoClientError']
