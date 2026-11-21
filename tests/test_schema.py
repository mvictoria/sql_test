from sqlglot import exp

from sql_test.engine.schema import Column


def test_casting_many_cells_parses_their_type_once(monkeypatch):
    builds = []
    build = exp.DataType.build

    def counting_build(*args, **kwargs):
        builds.append(args)
        return build(*args, **kwargs)

    monkeypatch.setattr(exp.DataType, "build", counting_build)
    column = Column(name="n", type="SMALLINT")

    assert [column.cast(str(i)) for i in range(1_000)] == list(range(1_000))
    assert len(builds) <= 1
