"""Shared generation foundations. Existing application routes remain unchanged."""

from .profile import BusinessProfile, ProfileError, ValidationIssue, profile_issues

__all__ = ['BusinessProfile', 'ProfileError', 'ValidationIssue', 'profile_issues']
