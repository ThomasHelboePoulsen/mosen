def format_count_bar_chart(fig, show_x_tick_labels=True):
    fig.update_layout(xaxis_title=None, yaxis_title="amount")
    fig.update_xaxes(showticklabels=show_x_tick_labels)
    fig.update_yaxes(dtick=1)
    return fig
