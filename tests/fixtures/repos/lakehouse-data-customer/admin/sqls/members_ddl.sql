create table members (
    member_id integer,
    member_name varchar(30),
    lob varchar(2)
);

create table lob (
    lob varchar(2),
    lob_name varchar(30)
);

create table medicaid_members (
    member_id integer,
    member_name varchar(30)
);

create table medicaid_members_named_alice (
    member_id integer,
    member_name varchar(30)
);
