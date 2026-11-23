-- noqa: disable=RF04,RF06
with latest_events as (
    select
        id,
        "source"
    from events
    qualify row_number() over (
        partition by id
        order by rowid desc
    ) = 1
)

select
    coalesce(latest_events.id, seen.id) as id,
    case
        when latest_events.id is not null then latest_events."source"
        else seen."source"
    end as "source"
from seen
full outer join latest_events
    on seen.id = latest_events.id
