from flask import jsonify
from . import flask_app, app



@flask_app.route("/<int:page_num>")
def get_page(page_num):
    try:
        return jsonify({
            "page": [g.get_json() for g in app.pages[page_num - 1]]
        })
    except IndexError:
        pass
