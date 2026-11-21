select
    staged_claims.claim_id,
    staged_claims.member_id,
    staged_members.member_name
from staged_claims
inner join staged_members
    on staged_claims.member_id = staged_members.member_id
