from unittest.mock import patch

import pytest


@pytest.fixture
def patch_ttk_widgets():
    with patch('app.replacements_editor.ttk.Button'), \
         patch('app.replacements_editor.ttk.Frame'), \
         patch('app.replacements_editor.ttk.Scrollbar'):
        yield
