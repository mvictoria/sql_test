create table raw_claims (
    claim_id integer,
    member_id integer
);

create table raw_members (
    member_id integer,
    member_name varchar(30)
);

create table staged_claims (
    claim_id integer,
    member_id integer
);

create table staged_members (
    member_id integer,
    member_name varchar(30)
);

create table member_claims (
    claim_id integer,
    member_id integer,
    member_name varchar(30)
);

create table customer_summary (
    member_id integer,
    claim_count integer
);
