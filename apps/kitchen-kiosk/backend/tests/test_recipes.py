RECIPE_MD = """# Banana Bread

## Ingredients
- 3 ripe bananas
- 1 cup sugar
- 2 cups flour

## Steps
1. Mash the bananas
2. Mix everything together
3. Bake at 180C for 50 minutes
"""


def test_recipes_list_returns_titles(client, tmp_path, monkeypatch):
    (tmp_path / 'banana-bread.md').write_text(RECIPE_MD)
    monkeypatch.setattr('recipes.RECIPES_DIR', str(tmp_path))

    response = client.get('/api/recipes')

    assert response.status_code == 200
    recipes = response.get_json()['recipes']
    assert recipes == [{'id': 'banana-bread', 'title': 'Banana Bread'}]


def test_recipe_detail_parses_ingredients_and_steps(client, tmp_path, monkeypatch):
    (tmp_path / 'banana-bread.md').write_text(RECIPE_MD)
    monkeypatch.setattr('recipes.RECIPES_DIR', str(tmp_path))

    response = client.get('/api/recipes/banana-bread')

    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Banana Bread'
    assert data['ingredients'] == ['3 ripe bananas', '1 cup sugar', '2 cups flour']
    assert data['steps'] == [
        'Mash the bananas',
        'Mix everything together',
        'Bake at 180C for 50 minutes',
    ]


def test_recipe_detail_404_for_missing_recipe(client, tmp_path, monkeypatch):
    monkeypatch.setattr('recipes.RECIPES_DIR', str(tmp_path))

    response = client.get('/api/recipes/does-not-exist')

    assert response.status_code == 404
