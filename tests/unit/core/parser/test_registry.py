import pytest
from codegraph.core.parser.registry import LanguageRegistry, LanguageSpec

def test_registry_registration_and_lookup():
    registry = LanguageRegistry()
    spec = LanguageSpec(name="testlang", extensions=(".test",), parser_cls=object, resolver_cls=object)
    registry.register(spec)
    
    assert registry.get_spec_by_extension(".test") is spec
    assert registry.get_spec_by_name("testlang") is spec
    
    with pytest.raises(KeyError):
        registry.get_spec_by_extension(".unknown")
