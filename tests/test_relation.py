import pytest

from sql_test.engine.relation import AmbiguousRelation, Relation


def test_parses_one_two_and_three_level_names():
    assert Relation.parse("lakehouse.claims.members") == Relation(
        catalog="lakehouse", schema="claims", name="members"
    )
    assert Relation.parse("claims.members") == Relation(schema="claims", name="members")
    assert Relation.parse("members") == Relation(name="members")


def test_normalizes_case_for_the_dialect():
    assert Relation.parse("Claims.Members") == Relation.parse("claims.members")


def test_a_shorter_name_resolves_to_the_one_relation_it_matches():
    known = [Relation.parse("lakehouse.claims.members"), Relation.parse("claims.lob")]

    assert Relation.parse("members").resolve(known) == Relation.parse(
        "lakehouse.claims.members"
    )
    assert Relation.parse("claims.members").resolve(known) == Relation.parse(
        "lakehouse.claims.members"
    )


def test_an_ambiguous_name_names_its_candidates():
    known = [Relation.parse("claims.members"), Relation.parse("billing.members")]

    with pytest.raises(AmbiguousRelation, match="billing.members.*claims.members"):
        Relation.parse("members").resolve(known)


def test_an_unknown_name_stays_as_written():
    known = [Relation.parse("claims.members")]

    assert Relation.parse("billing.members").resolve(known) == Relation.parse(
        "billing.members"
    )
