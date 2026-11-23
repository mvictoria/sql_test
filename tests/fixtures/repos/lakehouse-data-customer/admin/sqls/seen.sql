select
    id,
    source
from seen
union
select
    id,
    source
from events
where events.id not in (select seen.id from seen)
