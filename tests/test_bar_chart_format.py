from math import nan

import numpy as np
from plotly import graph_objects as go

from src.analytics.bar_chart_format import format_count_bar_chart


def _formatted_chart_with_values(values):
    fig = go.Figure()
    fig.add_bar(y=values)
    return format_count_bar_chart(fig)


def test_count_bar_chart_uses_integer_ticks_for_empty_chart():
    fig = format_count_bar_chart(go.Figure())

    assert fig.layout.yaxis.dtick == 1


def test_count_bar_chart_uses_small_decimal_ticks_for_average_values():
    assert _formatted_chart_with_values([0.4]).layout.yaxis.dtick == 0.1
    assert _formatted_chart_with_values([0.9]).layout.yaxis.dtick == 0.2


def test_count_bar_chart_uses_integer_ticks_for_small_counts():
    fig = _formatted_chart_with_values([1, 7, 14])

    assert fig.layout.yaxis.dtick == 1


def test_count_bar_chart_scales_ticks_for_larger_counts():
    assert _formatted_chart_with_values([20]).layout.yaxis.dtick == 2
    assert _formatted_chart_with_values([50]).layout.yaxis.dtick == 5
    assert _formatted_chart_with_values([100]).layout.yaxis.dtick == 10
    assert _formatted_chart_with_values([200]).layout.yaxis.dtick == 20


def test_count_bar_chart_ignores_missing_y_values_when_scaling_ticks():
    fig = _formatted_chart_with_values([None, nan, 8])

    assert fig.layout.yaxis.dtick == 1


def test_count_bar_chart_handles_array_y_values():
    fig = _formatted_chart_with_values(np.array([20, 30]))

    assert fig.layout.yaxis.dtick == 5
