select
    member_id,
    count(*) as claim_count
from member_claims
group by member_id
