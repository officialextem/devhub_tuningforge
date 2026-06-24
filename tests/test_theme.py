from app import theme


def test_log_level_colors_are_defined():
    assert theme.LOG_LEVEL_COLORS["INFO"] == theme.INFO
    assert theme.LOG_LEVEL_COLORS["SUCCESS"] == theme.SUCCESS
    assert theme.LOG_LEVEL_COLORS["WARNING"] == theme.WARNING
    assert theme.LOG_LEVEL_COLORS["ERROR"] == theme.ERROR
