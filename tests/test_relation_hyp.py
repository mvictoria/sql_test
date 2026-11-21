"""TEST-1: Relation.parse and resolve over random catalogs."""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from sql_test.engine.relation import AmbiguousRelation, Relation

_ident = st.from_regex(r"[a-z][a-z0-9]{0,7}", fullmatch=True)


@st.composite
def relation(draw: st.DrawFn) -> Relation:
    name = draw(_ident)
    kind = draw(st.sampled_from(("bare", "schema", "catalog")))
    if kind == "bare":
        return Relation(name=name)
    schema = draw(_ident)
    assume(schema != name)
    if kind == "schema":
        return Relation(name=name, schema=schema)
    catalog = draw(_ident)
    assume(catalog not in (name, schema))
    return Relation(name=name, schema=schema, catalog=catalog)


@given(relation())
def test_parse_round_trips_str(rel: Relation):
    assert Relation.parse(str(rel)) == rel


@given(st.lists(relation(), min_size=1, max_size=6, unique_by=str))
def test_a_unique_bare_name_resolves_to_the_only_match(known: list[Relation]):
    target = known[0]
    same_name = [r for r in known if r.name == target.name]
    assume(len(same_name) == 1)
    assert Relation(name=target.name).resolve(known) == target


@given(_ident, _ident, _ident)
def test_an_ambiguous_bare_name_names_its_candidates(
    name: str, schema_a: str, schema_b: str
):
    assume(schema_a != schema_b)
    assume(name not in (schema_a, schema_b))
    known = [
        Relation(name=name, schema=schema_a),
        Relation(name=name, schema=schema_b),
    ]
    with pytest.raises(AmbiguousRelation) as error:
        Relation(name=name).resolve(known)
    for candidate in known:
        assert str(candidate) in str(error.value)


@given(relation(), st.lists(relation(), max_size=5, unique_by=str))
def test_an_unknown_name_stays_as_written(probe: Relation, known: list[Relation]):
    assume(not any(probe.matches(r) for r in known))
    assert probe.resolve(known) == probe
