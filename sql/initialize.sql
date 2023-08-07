create table assignments
(
    assignment_id   integer
        primary key autoincrement,
    assignment_name text,
    base_dir        text,
    file_id_pointer integer
);

create table files
(
    file_id       integer
        primary key autoincrement,
    file_name     text,
    display_name  text,
    assignment_id integer
);

create table rubric
(
    assignment_id integer,
    rubric_json   text
);

create table scores
(
    assignment_id integer,
    file_id       integer,
    score_list    text,
    comment       text
);