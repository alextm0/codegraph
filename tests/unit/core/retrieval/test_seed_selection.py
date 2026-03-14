"""Unit tests for pure-function helpers in seed_selection.py."""

import pytest

from codegraph.core.retrieval.seed_selection import extract_entity_names


class TestExtractEntityNames:
    """Tests for extract_entity_names — no Neo4j required."""

    def test_camel_case_extracted(self):
        """CamelCase class names should be detected."""
        names = extract_entity_names("Fix the AuthService registration flow")
        assert "AuthService" in names

    def test_snake_case_extracted(self):
        """snake_case function names with underscores should be detected."""
        names = extract_entity_names("validate_email is broken for unicode input")
        assert "validate_email" in names

    def test_multi_word_camel_case(self):
        """Multi-word CamelCase like BlogPost should be extracted."""
        names = extract_entity_names("Update BlogPost and UserProfile models")
        assert "BlogPost" in names
        assert "UserProfile" in names

    def test_single_uppercase_word_not_extracted(self):
        """Single uppercase words ('Fix', 'Update') are not code identifiers."""
        names = extract_entity_names("Fix the bug")
        # 'Fix' is a single capitalized word, not multi-word CamelCase
        assert "Fix" not in names

    def test_all_caps_not_extracted(self):
        """ALL_CAPS constants are not matched by the snake_case pattern."""
        names = extract_entity_names("check TIMEOUT_MS constant")
        assert "TIMEOUT_MS" not in names

    def test_deduplication(self):
        """Each identifier appears only once even if mentioned multiple times."""
        names = extract_entity_names("validate_email: validate_email must handle None")
        assert names.count("validate_email") == 1

    def test_order_preserved(self):
        """CamelCase names appear before snake_case names in output."""
        names = extract_entity_names("AuthService calls validate_email")
        assert names.index("AuthService") < names.index("validate_email")

    def test_empty_string(self):
        """Empty input returns empty list."""
        assert extract_entity_names("") == []

    def test_no_identifiers(self):
        """Plain English with no code patterns returns empty list."""
        assert extract_entity_names("fix the bug in the login page") == []

    def test_mixed_content(self):
        """Both CamelCase and snake_case extracted from same text."""
        names = extract_entity_names(
            "The AuthService.register method calls validate_username and validate_password"
        )
        assert "AuthService" in names
        assert "validate_username" in names
        assert "validate_password" in names
