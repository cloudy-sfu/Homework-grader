select files.file_id, display_name, score_list is not null
from files left join scores
on files.file_id = scores.file_id and files.assignment_id = scores.assignment_id
where files.assignment_id = ?