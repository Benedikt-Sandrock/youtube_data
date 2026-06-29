"""
nahost_plot_utils.py

Shared plotting helper for the Nahost YouTube channel analysis scripts. One generic
function (`plot_group_trend`) covers every "metric per month, one line per group" plot
used across both analysis scripts - baseline-relative trends, decay/format/engagement
plots, and the panels of multi-panel figures (via the `ax` parameter).
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_group_trend(df_long, group_col, date_col, value_col, title, ylabel, plot_start,
                      event_date=None, reference_line=None, reference_label=None,
                      smooth=False, smooth_span=3, ax=None, show_legend=True):
    """
    Generic single-panel line plot of value_col over time, one line per group_col category.

    event_date        : if given, draws a vertical dotted line marking it (e.g. event day).
    reference_line     : if given (e.g. 100), draws a horizontal dashed reference line.
    reference_label    : legend label for that reference line.
    smooth              : if True, apply an exponentially-weighted moving average (span=smooth_span)
                          per group before plotting - useful for noisy monthly series.
    ax                  : pass an existing matplotlib Axes to draw into a multi-panel figure;
                          otherwise a new standalone figure is created and shown immediately.
    """
    standalone = ax is None
    plot_df = df_long[df_long[date_col] >= plot_start].copy()

    if smooth:
        plot_df[value_col] = (
            plot_df.groupby(group_col)[value_col]
            .transform(lambda x: x.ewm(span=smooth_span, adjust=False).mean())
        )

    if standalone:
        plt.figure(figsize=(14, 7))
        sns.set_theme(style="whitegrid")
        ax = plt.gca()

    sns.lineplot(data=plot_df, x=date_col, y=value_col, hue=group_col, marker="o",
                 linewidth=2, ax=ax, legend=show_legend)

    if reference_line is not None:
        ax.axhline(reference_line, color="red", linestyle="--", linewidth=1.5, label=reference_label)
    if event_date is not None:
        ax.axvline(pd.to_datetime(event_date), color="grey", linestyle=":", linewidth=1.5,
                   label="Event date")

    ax.set_title(title, fontsize=13 if standalone else 11)
    ax.set_xlabel("Month")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45)

    if standalone:
        if show_legend:
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        plt.show()
