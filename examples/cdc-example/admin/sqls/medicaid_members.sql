select
    members.member_id,
    members.member_name
from members
inner join lob on members.lob = lob.lob
where lob.lob_name = 'Medicaid'
