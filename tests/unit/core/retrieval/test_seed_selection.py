"""Unit tests for pure-function helpers in seed_selection.py."""

from unittest.mock import MagicMock

from codegraph.core.retrieval.seed_selection import (
    _match_entities,
    extract_entity_names,
    tokenize,
)


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


class TestExtractEntityNamesEnhanced:
    """Tests for the extended entity extraction patterns."""

    def test_single_camel_with_internal_upper(self):
        """Single-word CamelCase with internal uppercase should be extracted."""
        names = extract_entity_names("QuerySet is broken")
        assert "QuerySet" in names

    def test_backtick_quoted_identifier(self):
        """Backtick-quoted identifiers from GitHub markdown should be extracted."""
        names = extract_entity_names("check `models.QuerySet` behavior")
        assert "models.QuerySet" in names

    def test_dotted_path(self):
        """Dotted module paths should be extracted."""
        names = extract_entity_names("the sql.compiler module has a bug")
        assert "sql.compiler" in names

    def test_all_caps_still_not_extracted(self):
        """ALL_CAPS identifiers must remain excluded."""
        names = extract_entity_names("check TIMEOUT_MS constant")
        assert "TIMEOUT_MS" not in names

    def test_sql_compiler_camel(self):
        """SQLCompiler should be extracted as a single-CamelCase identifier."""
        names = extract_entity_names("SQLCompiler is broken")
        assert "SQLCompiler" in names


class TestTokenize:
    """Tests for the compound-splitting tokenizer."""

    def test_camel_case_split(self):
        """CamelCase identifiers should split into lowercase tokens."""
        assert tokenize("SQLCompiler") == ["sql", "compiler"]

    def test_pascal_case_split(self):
        """PascalCase identifiers should split into lowercase tokens."""
        assert tokenize("HandleSubQuery") == ["handle", "sub", "query"]

    def test_snake_case_split(self):
        """snake_case identifiers should split on underscores."""
        assert tokenize("handle_subquery") == ["handle", "subquery"]

    def test_https_connection(self):
        """Consecutive uppercase runs followed by title case should split correctly."""
        assert tokenize("HTTPSConnection") == ["https", "connection"]

    def test_single_char_filtered(self):
        """Single-character tokens should be filtered out."""
        assert "a" not in tokenize("a b c word")

    def test_plain_text_tokens(self):
        """Plain English words should be tokenized normally."""
        tokens = tokenize("fix the auth timeout bug")
        assert "fix" in tokens
        assert "auth" in tokens
        assert "timeout" in tokens


class TestMatchEntitiesExcludePaths:
    """Verify entity match passes exclude_paths into Cypher."""

    def test_exclude_paths_forwarded_to_cypher(self):
        driver = MagicMock()
        session = MagicMock()
        driver.session.return_value.__enter__.return_value = session
        session.run.return_value = []

        _match_entities(
            driver,
            ["User"],
            base_weight=0.6,
            exclude_paths=["tests/", "test_"],
        )

        _, kwargs = session.run.call_args
        assert kwargs["exclude_paths"] == ["tests/", "test_"]
        query = session.run.call_args[0][0]
        assert "exclude_paths" in query
