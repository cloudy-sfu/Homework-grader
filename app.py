import json
import os
import sqlite3
import webbrowser
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect
from winapi import select_folder


def write_sql(db_path, sql, *args):
    c = sqlite3.connect(db_path)
    r = c.cursor()
    r.execute(sql, args)
    r.close()
    c.commit()
    c.close()


def read_sql(db_path, sql, *args, one=False):
    c = sqlite3.connect(db_path)
    r = c.cursor()
    r.execute(sql, args)
    rst = r.fetchone() if one else r.fetchall()
    r.close()
    c.close()
    return rst


app = Flask(__name__)
config_db = "scores.db"
supported_file_types = ('.htm', '.html', '.pdf', '.txt')

if not os.path.exists(config_db):
    with open("sql/initialize.sql", "r") as f:
        commands = f.read().split(';')
        for command in commands:
            write_sql(config_db, command)
with open("sql/check_files_scored.sql", "r") as f:
    check_files_scored = f.read()


@app.route('/', methods=['GET'])
def index():
    assignments = read_sql(config_db, "SELECT assignment_id, assignment_name FROM assignments")
    return render_template('index.html', existed_configs=assignments)


@app.route('/delete-config', methods=['GET'])
def delete_config():
    agn_id = request.args.get('id')
    if agn_id:
        write_sql(config_db, "DELETE FROM assignments WHERE assignment_id = ?", agn_id)
        write_sql(config_db, "DELETE FROM files WHERE assignment_id = ?", agn_id)
        write_sql(config_db, "DELETE FROM rubric WHERE assignment_id = ?", agn_id)
        write_sql(config_db, "DELETE FROM scores WHERE assignment_id = ?", agn_id)
    return redirect('/')


@app.route('/config-add', methods=['POST'])
def config_add():
    name = request.form.get('name')
    if not name:
        return 'Assignment name is empty.'
    n_existed = read_sql(config_db, "SELECT count(*) FROM assignments WHERE assignment_name = ?", name, one=True)
    n_existed = n_existed[0]
    if n_existed == 0:
        write_sql(config_db, "INSERT INTO assignments (assignment_name) VALUES (?)", name)
    agn_id = read_sql(config_db, "SELECT assignment_id FROM assignments WHERE assignment_name = ?", name, one=True)
    agn_id = agn_id[0]
    base_dir = request.form.get('base_dir')
    if not (base_dir and os.path.isdir(base_dir)):
        return 'The base directory doesn\'t exist.'
    for fn in os.listdir(base_dir):
        display_name, ext_name = os.path.splitext(fn)
        if ext_name in supported_file_types:
            write_sql(config_db, "INSERT INTO files (file_name, display_name, assignment_id) VALUES (?, ?, ?)",
                      fn, display_name, agn_id)
    pointer = read_sql(config_db, "SELECT min(file_id) FROM files WHERE assignment_id = ?", agn_id, one=True)
    pointer = pointer[0]
    if pointer:
        write_sql(config_db, "UPDATE assignments SET base_dir = ?, file_id_pointer = ? WHERE assignment_id = ?",
                  base_dir, pointer, agn_id)
    else:
        return f'The base directory is empty. Supported file types: {supported_file_types}.'
    return redirect('/')


@app.route('/select-base-directory', methods=['GET'])
def select_base_directory():
    base_dir = select_folder()
    if base_dir:
        return {'error': 0, 'base_dir': base_dir, 'message': ''}
    else:
        return {'error': 1, 'base_dir': '', 'message': 'Selected base directory doesn\'t exist.'}


@app.route('/rubric', methods=['GET'])
def rubric():
    agn_id = request.args.get('id')
    agn_name = read_sql(config_db, "SELECT assignment_name FROM assignments WHERE assignment_id = ?", agn_id, one=True)
    if not agn_name:
        return 'Assignment doesn\'t exist.'
    agn_name = agn_name[0]
    rubric_json = read_sql(config_db, "SELECT rubric_json FROM rubric WHERE assignment_id = ?", agn_id, one=True)
    if rubric_json:
        rubric_json = json.loads(rubric_json[0])
    else:
        rubric_json = []
    return render_template(
        'rubric.html', rubric=rubric_json, display_name=agn_name,
        agn_id=agn_id,
    )


@app.route('/rubric-edit', methods=['POST'])
def rubric_edit():
    agn_id = request.form.get('agn_id')
    rubric_json = []
    try:
        for caption in request.form.keys():
            if caption.startswith('caption-'):
                q_id = caption.removeprefix('caption-')
                question = {
                    'q_id': q_id,
                    'caption': request.form.get(caption),
                    'assessment': []
                }
                for score in request.form.keys():
                    if score.startswith(f'score-{q_id}-'):
                        a_id = score.removeprefix(f'score-{q_id}-')
                        level = {
                            'score': float(request.form.get(score)),
                            'definition': request.form.get(f'def-{q_id}-{a_id}')
                        }
                        question['assessment'].append(level)
                question['assessment'] = sorted(question['assessment'], key=lambda lv: lv['score'], reverse=True)
                rubric_json.append(question)
    except (KeyError, ValueError, TypeError):
        return 'Submitted data is invalid.'
    rubric_json = json.dumps(rubric_json)
    existed = read_sql(config_db, "SELECT * FROM rubric WHERE assignment_id = ?", agn_id)
    if existed:
        write_sql(config_db, "UPDATE rubric SET rubric_json = ? WHERE assignment_id = ?", rubric_json, agn_id)
    else:
        write_sql(config_db, "INSERT INTO rubric (assignment_id, rubric_json) VALUES (?, ?)", agn_id, rubric_json)
    return redirect('/')


@app.route('/grade', methods=['GET'])
def grade():
    agn_id = request.args.get('id')
    try:
        title, file_id, base_dir = read_sql(
            config_db, "SELECT assignment_name, file_id_pointer, base_dir FROM assignments WHERE assignment_id = ?",
            agn_id, one=True
        )
    except TypeError:
        return 'Assignment doesn\'t exist.'
    filelist = read_sql(config_db, check_files_scored, agn_id)
    if not filelist:
        return 'Base directory is empty.'
    max_file_id = max(x[0] for x in filelist)
    rubric_ = read_sql(config_db, "SELECT rubric_json FROM rubric WHERE assignment_id = ?", agn_id, one=True)
    if rubric_:
        rubric_ = json.loads(rubric_[0])
    else:
        rubric_ = []
    score_comment = read_sql(config_db,
                             "SELECT score_list, comment FROM scores WHERE assignment_id = ? AND file_id = ?",
                             agn_id, file_id, one=True)
    if score_comment:
        raw_score, comment = json.loads(score_comment[0]), score_comment[1]
        score = []
        for s, q in zip(raw_score, rubric_):
            levels = [m['score'] for m in q['assessment']]
            score.append((s, s in levels))
    else:
        score, comment = [], ''
    return render_template(
        'grade.html', title=title, file_id=file_id, filelist=filelist,
        rubric=rubric_, agn_id=agn_id, current_score=score, note=comment, n=max_file_id,
    )


@app.route('/grade-file', methods=['GET'])
def view_file():
    file_id = request.args.get('file_id')
    agn_id = request.args.get('assignment_id')
    try:
        base_dir, file_name = read_sql(config_db, "SELECT base_dir, file_name FROM assignments a JOIN files f "
                                                  "ON a.assignment_id = f.assignment_id WHERE file_id = ? AND "
                                                  "a.assignment_id = ?", file_id, agn_id, one=True)
        file_path = os.path.abspath(os.path.join(base_dir, file_name))
        assert os.path.isfile(file_path)
    except (TypeError, AssertionError):
        return 'File does not exist.'
    return send_file(file_path)


@app.route('/grade-jump', methods=['POST'])
def grade_jump():
    agn_id = request.form.get('agn_id')
    file_id = request.form.get('file_id')
    files = read_sql(config_db, "SELECT file_id FROM files WHERE assignment_id = ?", agn_id)
    files = [x[0] for x in files]
    try:
        file_id = int(file_id)
    except TypeError:
        return 'Do not customize POST information. (File ID is not an integer.)'
    if file_id not in files:
        return 'File doesn\'t exist.'
    write_sql(config_db, "UPDATE assignments SET file_id_pointer = ? WHERE assignment_id = ?",
              file_id, agn_id)
    return redirect(f'/grade?id={agn_id}')


@app.route('/grade-update', methods=['POST'])
def grade_submit():
    agn_id = read_sql(
        config_db, "SELECT assignment_id FROM assignments WHERE assignment_id = ?",
        request.form.get('agn_id'), one=True
    )
    if not agn_id:
        return 'Assignment doesn\'t exist.'
    agn_id = agn_id[0]
    file_id = read_sql(
        config_db, "SELECT file_id FROM files WHERE file_id = ?",
        request.form.get('student_id'), one=True
    )
    if not file_id:
        return 'File doesn\'t exist.'
    file_id = file_id[0]
    action = request.form.get('action')
    if action == 'Save and continue':
        next_file_id = read_sql(config_db, "SELECT min(file_id) FROM files WHERE assignment_id = ? AND file_id > ?",
                                agn_id, file_id, one=True)
        if next_file_id:
            write_sql(config_db, "UPDATE assignments SET file_id_pointer = ? WHERE assignment_id = ?",
                      next_file_id[0], agn_id)
    config = read_sql(config_db, 'SELECT rubric_json FROM rubric WHERE assignment_id = ?', agn_id, one=True)
    try:
        config = json.loads(config[0])
        score = []
        for q in config:
            raw_score = request.form.get(q['q_id'])
            if raw_score == 'c':  # customized
                s = float(request.form.get(q['q_id'] + '-c'))
            else:
                s = float(raw_score)
            score.append(s)
        comment = request.form.get('note')
        n_existed = read_sql(config_db, "SELECT count(*) FROM scores WHERE assignment_id = ? AND file_id = ?",
                             agn_id, file_id, one=True)
        n_existed = n_existed[0]
        if n_existed == 0:
            write_sql(config_db, "INSERT INTO scores (assignment_id, file_id, score_list, comment) VALUES (?, ?, ?, ?)",
                      agn_id, file_id, json.dumps(score), comment)
        else:
            write_sql(config_db, "UPDATE scores SET score_list = ?, comment = ? WHERE assignment_id = ? AND file_id = ?",
                      json.dumps(score), comment, agn_id, file_id)
    except (TypeError, ValueError, KeyError):
        return 'Submitted data is invalid.'
    return redirect(f'/grade?id={agn_id}')


@app.route('/analyze', methods=['GET'])
def analyze():
    agn_id = request.args.get('id')
    assignment_name = read_sql(config_db, "SELECT assignment_name FROM assignments WHERE assignment_id = ?",
                               agn_id, one=True)
    if not assignment_name:
        return 'Assignment doesn\'t exist.'
    assignment_name = assignment_name[0]
    rubric_ = read_sql(config_db, "SELECT rubric_json FROM rubric WHERE assignment_id = ?", agn_id, one=True)
    if not rubric_:
        return 'Rubric doesn\'t exist.'
    rubric_ = json.loads(rubric_[0])
    questions = [q.get('caption', 'No caption') for q in rubric_]

    c = sqlite3.connect(config_db)
    raw_scores = pd.read_sql(con=c, sql="SELECT display_name, score_list, comment FROM files JOIN scores "
                                        "ON files.file_id = scores.file_id")
    c.close()
    scores = pd.DataFrame(
        data=raw_scores['score_list'].apply(json.loads).tolist(),
        columns=questions
    )
    scores.index = raw_scores['display_name']
    notes = raw_scores[['comment']].copy()
    notes.index = raw_scores['display_name']
    notes.replace('', pd.NA, inplace=True)
    notes.dropna(inplace=True)
    return render_template(
        'analyze.html',
        caption=assignment_name,
        scores=scores.to_html(
            classes='table table-bordered table-striped',
            float_format=lambda g: format(g, 'g'),
            na_rep='', index_names=False,
        ),
        notes=notes.to_html(
            classes='table table-bordered table-striped',
            index_names=False,
        ),
    )


if __name__ == '__main__':
    webbrowser.open_new_tab('http://localhost:5000')
    app.run()
