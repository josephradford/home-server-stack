"""Parses a folder of hand-edited recipe markdown files into structured JSON.
No in-place editing UI - files are edited directly on the server."""
import os
import re
from pathlib import Path

from flask import Blueprint, jsonify

recipes_bp = Blueprint('recipes', __name__)

RECIPES_DIR = os.getenv('KIOSK_RECIPES_DIR', '/recipes')


def _recipe_path(recipe_id):
    return Path(RECIPES_DIR) / f'{recipe_id}.md'


def _parse_recipe(text):
    """Expects:
    # Title
    ## Ingredients
    - item
    ## Steps
    1. step
    """
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else 'Untitled'

    ingredients_match = re.search(r'##\s*Ingredients\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
    ingredients = []
    if ingredients_match:
        ingredients = [
            line.lstrip('-* ').strip()
            for line in ingredients_match.group(1).strip().splitlines()
            if line.strip()
        ]

    steps_match = re.search(r'##\s*Steps\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
    steps = []
    if steps_match:
        steps = [
            re.sub(r'^\d+\.\s*', '', line).strip()
            for line in steps_match.group(1).strip().splitlines()
            if line.strip()
        ]

    return title, ingredients, steps


@recipes_bp.route('/api/recipes')
def list_recipes():
    result = []
    recipes_dir = Path(RECIPES_DIR)
    if recipes_dir.is_dir():
        for path in sorted(recipes_dir.glob('*.md')):
            text = path.read_text()
            title, _, _ = _parse_recipe(text)
            result.append({'id': path.stem, 'title': title})
    return jsonify({'recipes': result})


@recipes_bp.route('/api/recipes/<recipe_id>')
def recipe_detail(recipe_id):
    path = _recipe_path(recipe_id)
    if not path.is_file():
        return jsonify({'error': 'recipe not found'}), 404

    title, ingredients, steps = _parse_recipe(path.read_text())
    return jsonify({'id': recipe_id, 'title': title, 'ingredients': ingredients, 'steps': steps})
