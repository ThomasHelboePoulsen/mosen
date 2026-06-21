from math import floor, isfinite, log10


def format_count_bar_chart(fig, show_x_tick_labels=True):
    fig.update_layout(xaxis_title=None, yaxis_title="amount")
    fig.update_xaxes(showticklabels=show_x_tick_labels)
    fig.update_yaxes(dtick=count_bar_chart_dtick(fig))
    return fig


def count_bar_chart_dtick(fig):
    max_value = max(_finite_y_values(fig), default=0)

    if max_value < 1:
        if max_value <= 0:
            return 1
        return 0.1 if max_value <= 0.5 else 0.2

    if max_value < 15:
        return 1

    return _nice_tick(max_value / 10)


def _finite_y_values(fig):
    for trace in fig.data:
        if trace.y is None:
            continue

        for value in trace.y:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue

            if isfinite(number):
                yield number


def _nice_tick(raw_tick):
    exponent = floor(log10(raw_tick))
    scale = 10**exponent
    fraction = raw_tick / scale

    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10

    return nice_fraction * scale
