import re
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect
import os
import json
import webbrowser

app = Flask(__name__)
assignments = './assignments/'
os.makedirs(assignments, exist_ok=True)
supported_file_types = ('.htm', '.html', '.pdf', '.txt')


@app.route('/', methods=['GET'])
def index():  # put application's code here
    existed_configs = [fn for fn in os.listdir(assignments) if os.path.splitext(fn)[1] == '.json']
    return render_template('index.html', existed_configs=existed_configs)


@app.route('/delete-config', methods=['GET'])
def delete_config():
    config_path = os.path.join(assignments, request.args.get('name', ''))
    if os.path.isfile(config_path):
        os.remove(config_path)
    return redirect('/')


@app.route('/export-config', methods=['GET'])
def export_config():
    config_path = os.path.join(assignments, request.args.get('config', ''))
    if os.path.isfile(config_path):
        return send_file(config_path, as_attachment=True)
    else:
        return redirect('/')


@app.route('/import-config', methods=['POST'])
def import_config():
    config = request.files['config']
    json_name = config.filename
    cand_saved_path = os.path.join(assignments, json_name)
    if os.path.exists(cand_saved_path):
        return 'Config file has already existed.'
    config.save(cand_saved_path)
    return redirect('/')


def config_pull(config_name):
    if not config_name:
        return
    config_path = os.path.join(assignments, config_name)
    if not os.path.isfile(config_path):
        return
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config


def config_push(config_name, config_content):
    if not config_name:
        return
    config_path = os.path.join(assignments, config_name)
    with open(config_path, 'w') as f:
        json.dump(config_content, f, indent=4)


@app.route('/config-add', methods=['POST'])
def config_add():
    name = request.form.get('name')
    if not name:
        return 'Name is empty.'
    json_name = re.sub(r'\s', '_', name).lower() + '.json'
    cand_saved_path = os.path.join(assignments, json_name)
    if os.path.exists(cand_saved_path):
        return 'Config file has already existed.'
    config = {'base_dir': '', 'name': name, 'rubric': [], 'scores': {}, 'notes': {},
              'id': 0, 'filenames': []}
    config_push(json_name, config)
    return redirect('/')


@app.route('/config-check-name', methods=['POST'])
def config_check_name():
    config_name = request.form.get('config_name')
    config = config_pull(config_name)
    if not config:
        return 'Config doesn\'t exist.'
    base_dir = request.form.get('base_dir')
    if not (base_dir and os.path.isdir(base_dir)):
        return 'The base directory does not exist.'
    config['base_dir'] = base_dir
    assignment_file_names = [fn for fn in os.listdir(base_dir) if os.path.splitext(fn)[1] in supported_file_types]
    if not assignment_file_names:
        return f'The base directory is empty. Supported file types {supported_file_types}.'
    config["filenames"] = assignment_file_names
    rebuild = request.form.get('rebuild')
    if rebuild:
        config['scores'] = {}
        config['notes'] = {}
    config_push(config_name, config)
    return redirect('/')


@app.route('/config-rubric', methods=['POST'])
def config_rubric():
    config_name = request.form.get('config_name')
    config = config_pull(config_name)
    if not config:
        return 'Config doesn\'t exist.'
    try:
        config['rubric'] = []
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
                config['rubric'].append(question)
    except (KeyError, ValueError, TypeError):
        return 'Submitted data is invalid.'
    config_push(config_name, config)
    return redirect('/')


@app.route('/config-fork', methods=['GET'])
def config_fork():
    config_name = request.args.get('config')
    config = config_pull(config_name)
    if not config:
        return 'Config file does not exist.'
    return render_template(
        'config.html', rubric=config.get('rubric'), display_name=config.get('name'),
        config_name=config_name,
    )


@app.route('/grade', methods=['GET'])
def grade():
    config_name = request.args.get('config')
    config = config_pull(config_name)
    if not config:
        return 'Config file does not exist.'
    id_ = config.get('id')
    filenames = config.get('filenames')
    n = len(filenames)
    try:
        scores = config['scores']
        filelist = [(filenames[i], str(i) in scores.keys()) for i in range(n)]
        id_str = str(id_)
        if id_str in scores.keys():
            raw_scores = config['scores'][id_str]
            questions = config['rubric']
            scores = []
            for s, q in zip(raw_scores, questions):
                levels = [m['score'] for m in q['assessment']]
                scores.append((s, s in levels))
        else:
            scores = []
        note = config['notes'].get(id_str, '')
    except KeyError:
        return 'Config file is invalid.'
    return render_template(
        'grade.html',
        title=config.get('name'), id=id_, config=config_name, rubric=config.get('rubric'),
        current_score=scores, filelist=filelist, note=note,
    )


@app.route('/grade-file', methods=['GET'])
def grade_file():
    config_name = request.args.get('config')
    config = config_pull(config_name)
    if not config:
        return 'Config file does not exist.'
    filenames = config.get('filenames')
    base_dir = config.get('base_dir')
    id_ = config.get('id')
    try:
        current_file = filenames[id_]
        current_file = os.path.abspath(os.path.join(base_dir, current_file))
    except (TypeError, IndexError):
        return 'File does not exist.'
    if os.path.isfile(current_file):
        return send_file(current_file)
    else:
        return 'File does not exist.'


@app.route('/grade-jump', methods=['POST'])
def grade_jump():
    config_name = request.form.get('config')
    config = config_pull(config_name)
    if not config:
        return 'Config file does not exist.'
    try:
        config['id'] = int(request.form.get('id'))
    except (TypeError, ValueError):
        return 'Submitted data is invalid.'
    config_push(config_name, config)
    return redirect('/grade?config=' + config_name)


@app.route('/grade-update', methods=['POST'])
def grade_submit():
    config_name = request.form.get('config')
    config = config_pull(config_name)
    if not config:
        return 'Config file does not exist.'
    id_str = request.form.get('student-id')
    action = request.form.get('action')
    try:
        id_ = int(id_str)
        if action == 'Save and continue':
            config['id'] = id_ + 1
        config['scores'][id_str] = []
        for q in config['rubric']:
            raw_score = request.form.get(q['q_id'])
            if raw_score == 'c':  # customized
                score = float(request.form.get(q['q_id'] + '-c'))
            else:
                score = float(raw_score)
            config['scores'][id_str].append(score)
        note = request.form.get('note')
        if note:
            config['notes'][id_str] = note
    except (TypeError, ValueError, KeyError):
        return 'Submitted data is invalid.'
    config_push(config_name, config)
    return redirect('/grade?config=' + config_name)


@app.route('/analyze', methods=['GET'])
def analyze():
    config_name = request.args.get('config')
    config = config_pull(config_name)
    if not config:
        return 'Config file does not exist.'
    columns = [q.get('caption', 'No caption') for q in config.get('rubric', [])]
    try:
        filenames, _ = zip(*map(os.path.splitext, config.get('filenames')))
    except ValueError:
        return 'The directory is empty.'
    scores = pd.DataFrame(index=filenames, columns=columns)
    notes = pd.DataFrame(index=filenames, columns=['Note'])
    for k, v in config.get('scores', {}).items():
        try:
            row_id = int(k) % len(filenames)
        except ValueError:
            continue
        scores.iloc[row_id, :] = v
    for k, v in config.get('notes', {}).items():
        try:
            row_id = int(k) % len(filenames)
        except ValueError:
            continue
        notes['Note'][row_id] = v
    return render_template(
        'analyze.html',
        caption=config.get('name'),
        scores=scores.to_html(
            classes='table table-bordered table-striped',
            float_format=lambda f: format(f, 'g'),
            na_rep='',
        ),
        notes=notes.to_html(
            classes='table table-bordered table-striped',
            na_rep='',
        ),
    )


if __name__ == '__main__':
    webbrowser.open_new_tab('http://localhost:5000')
    app.run()
