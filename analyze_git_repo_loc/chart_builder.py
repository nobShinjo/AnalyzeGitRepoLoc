"""
A module for building and displaying LOC (Lines of Code) trend charts using Plotly.
This module defines the `ChartBuilder` class, which provides methods to set data,
create various types of traces (area, line, bar), and update the layout of a Plotly
figure. The class supports method chaining for a fluid interface pattern, allowing
for dynamic updates and modifications of the visualization.

Classes:
    ChartBuilder: A class responsible for building and displaying LOC trend by language
                  and total LOC charts.

Usage example:
        .create_fig()
        .create_trend_trace(xaxis_column="Date")
        .create_sum_trace(xaxis_column="Date")
        .create_bar_trace(xaxis_column="Date")
        .update_fig(sub_title="My Subtitle")
        .update_xaxis_tickformat(interval="monthly")
    chart_builder.show()
"""

from typing import TypeVar

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ChartBuilder:
    """
    A class responsible for building and displaying LOC trend by language and total LOC charts.
    """

    ChartBuilderSelf = TypeVar("ChartBuilderSelf", bound="ChartBuilder")

    def __init__(self) -> None:
        """
        Initializes a new instance of the ChartBuilder class without any data.

        Initialization sets up three primary instance attributes intended to be populated
        with data later on. The _trend_data and _sum_data are placeholders for DataFrame
        objects containing chart data, while _fig is intended to hold a Plotly figure object.
        """
        self._trend_data: pd.DataFrame
        """ A DataFrame containing the trend data of LOC. """
        self._summary_data: pd.DataFrame
        """ A DataFrame containing the summary data of LOC and the difference of LOC. """
        self._fig: go.Figure = None
        """ The final Plotly figure object that contains the combined area and line plot. """

    def set_trend_data(self, trend_data: pd.DataFrame) -> ChartBuilderSelf:
        """
        Sets the trend data for the chart builder.

        The method assigns the provided pandas DataFrame to the `_trend_data` attribute,
        which presumably is used to build or update a chart figure.

        Args:
            trend_data (pd.DataFrame): The data frame containing trend information
                                       to be visualized.

        Returns:
            ChartBuilderSelf: The instance itself, enabling method chaining.

        This method enables the caller to input new data into the chart builder instance,
        allowing for dynamic updates and modifications of the visualization.
        """
        self._trend_data = trend_data
        return self

    def set_summary_data(self, summary_data: pd.DataFrame) -> ChartBuilderSelf:
        """
        Sets the summary data for the chart builder.

        This method assigns the provided pandas DataFrame to the `_sum_data` attribute,
        which is likely used for representing aggregate or summary statistics in a chart.

        Args:
            summary_data (pd.DataFrame): A DataFrame containing the summary data.

        Returns:
            ChartBuilderSelf: The instance of the chart builder. This allows for chaining
                              method calls to configure the chart builder further.

        Example usage might involve setting up a series of configurations to a chart builder:
        ```
        chart_builder = (
            ChartBuilder()
            .set_trend_data(trend_frame)
            .set_summary_data(summary_frame)
            ...
        )
        ```

        By enabling this fluid interface pattern, the chart builder can progressively be
        configured with different data components for a final visualization.
        """
        self._summary_data = summary_data
        return self

    def create_fig(self) -> ChartBuilderSelf:
        """
        Initializes a figure object with a single subplot for the chart.

        The method sets the `_fig` attribute of the instance to a new figure
        with predefined x and y axis titles set to "Date" and "LOC" respectively.

        Returns:
            ChartBuilderSelf: The instance itself, allowing for method chaining.

        This is typically used to prepare the plotting object before adding traces,
        layouts or other specific settings required for the final visualization. After calling
        this method, additional configurations can be applied on the `_fig` attribute.
        """
        self._fig: go.Figure = make_subplots(
            rows=1,
            cols=1,
            specs=[[{"secondary_y": True}]],
        )
        return self

    def create_trend_trace(self, xaxis_column: str) -> ChartBuilderSelf:
        """
        Generates a trend trace from the trend data and appends it to the chart figure.

        This method creates an area plot representing the trends of lines of code (LOC)
        by language over time using the `_trend_data` attribute. It then extracts the
        traces from that plot and appends each trace to the first row and column of the
        main figure maintained by this instance (`_fig`).

        The plot is presumably created using Plotly Express, which is indicated by the `px`
        prefix on the `area()` function.

        Args:
            xaxis_column (str): The name of the column in the trend data frame that contains
                                the x-axis data for the area plot.

        Returns:
            ChartBuilderSelf: The instance of the chart builder with the new trend trace
                                appended to its figure. This supports chaining further
                                configuration calls to the chart builder.

        Example usage might involve creating a trend trace as part of configuring a chart builder:
        ```
        chart_builder = (
            ChartBuilder()
            .set_trend_data(trend_frame)
            .create_trend_trace()
            ...
        )
        ```

        This docstring assumes that `_trend_data` and `_fig` are pre-existing attributes of the
        instance that have been appropriately set. `_trend_data` should be a DataFrame containing
        the necessary data for plotting, while `_fig` should be a Plotly figure object that can
        have traces appended to it.
        """
        # Field area plot of LOC trend
        fig_lang = px.area(
            data_frame=self._trend_data,
            x=xaxis_column,
            y=self._trend_data.columns[1:],
            line_shape=None,
        )
        fig_lang_traces = []
        for trace in range(len(fig_lang["data"])):
            fig_lang_traces.append(fig_lang["data"][trace])

        for traces in fig_lang_traces:
            self._fig.append_trace(traces, row=1, col=1)

        return self

    def create_sum_trace(self, xaxis_column: str) -> ChartBuilderSelf:
        """
        Creates and appends a summary line trace to the chart figure.

        This method uses the `_sum_data` attribute to generate a line plot with markers
        representing the total lines of code (LOC) trend. Each trace generated from
        `fig_sum` is then configured to not show a legend entry by setting the
        'showlegend' property to False. The traces are collected in a list and
        subsequently appended to the main figure's first row and column.

        Args:
            xaxis_column (str): The name of the column in the summary data frame that contains
                                the x-axis data for the line plot.

        Returns:
            ChartBuilderSelf: The instance itself is returned, enabling method chaining
                              with other configuration functions of the chart builder.

        Example usage might be:
        ```
        chart_builder = (
            ChartBuilder()
            .set_sum_data(summary_data_frame)
            .create_sum_trace()
            ...
        )
        ```

        This docstring assumes there is an internal representation for the chart in the form
        of `_sum_data`, which should be a pandas DataFrame containing the data needed for the
        plot, and `_fig`, which should be a Plotly figure object available for appending
        traces to it.
        """
        # Line plots of total LOC trend
        fig_sum = px.line(
            data_frame=self._summary_data, x=xaxis_column, y="SUM", markers=True
        )
        for trace in fig_sum["data"]:
            # trace["showlegend"] = False
            trace["name"] = "SUM"
            trace["marker"] = {"size": 8, "color": "#636EFA"}
            trace["line"] = {"width": 2, "color": "#636EFA"}
            self._fig.add_trace(trace, row=1, col=1, secondary_y=False)

        return self

    def create_diff_trace(self, xaxis_column: str) -> ChartBuilderSelf:
        """
        Adds a differential trace to an existing plotly figure within the ChartBuilder instance.

        This method creates a line chart using the internal summed data
        focusing on the 'Diff' column.
        It then adds this newly created trace to the main figure without including it in the legend.
        The trace is placed on a secondary y-axis in the first row and column of the subplot grid.

        Args:
            xaxis_column (str): The name of the column in the summary data frame that contains
                                the x-axis data for the line plot.

        Returns:
            self (ChartBuilder): Returns the instance itself for method chaining purposes.
        """
        fig_diff = px.line(
            data_frame=self._summary_data, x=xaxis_column, y="Diff", markers=True
        )
        for trace in fig_diff["data"]:
            # trace["showlegend"] = False
            trace["name"] = "Diff"
            trace["marker"] = {"size": 8, "color": "#EF553B"}
            trace["line"] = {"width": 2, "color": "#EF553B"}
            self._fig.add_trace(trace, row=1, col=1, secondary_y=True)
        return self

    # added, deleted の棒グラフを追加するメソッド
    def create_bar_trace(self, xaxis_column: str) -> ChartBuilderSelf:
        """
        Adds a bar trace to an existing plotly figure within the ChartBuilder instance.

        This method creates a bar chart using the internal summed data
        focusing on the 'NLOC_Added' and 'NLOC_Deleted' columns.
        It then adds this newly created trace to the main figure without including it in the legend.
        The trace is placed on a secondary y-axis in the first row and column of the subplot grid.

        Args:
            xaxis_column (str): The name of the column in the summary data frame that contains
                                the x-axis data for the line plot.

        Returns:
            self (ChartBuilder): Returns the instance itself for method chaining purposes.
        """
        fig_bar = px.bar(
            data_frame=self._summary_data,
            x=xaxis_column,
            y=["Added", "Deleted"],
            barmode="relative",
        )

        # Add the bar traces to the figure
        for trace in fig_bar["data"]:
            # trace["showlegend"] = False
            self._fig.add_trace(trace, row=1, col=1, secondary_y=True)

        # Update the color of the bar traces
        added_trace, deleted_trace = self._fig.data[-2], self._fig.data[-1]
        added_trace.marker.color = "rgba(0,204,150,0.6)"
        deleted_trace.marker.color = "rgba(239,85,59,0.6)"
        for trace in [added_trace, deleted_trace]:
            trace.marker.line.width = 1
            trace.marker.line.color = "rgba(0,0,0,0)"

        return self

    def update_fig(self, sub_title: str) -> ChartBuilderSelf:
        """
        Updates the axes and layout of the `_fig` attribute with a specific style.

        This method configures various properties for both x and y axes, such as
        visibility of grid lines, color and width of lines, angle and format of ticks,
        as well as updating the layout of the figure to adjust background color, title,
        and legend styling.

        Args:
            sub_title (str): The subtitle to be displayed in the chart title.

        Returns:
            ChartBuilderSelf: The instance itself, enabling method chaining.

        After the call to this method, the `_fig` attribute will be styled according to
        the specifications set within this method and can be further manipulated or displayed.
        """
        self._fig.update_xaxes(
            showline=True,
            linewidth=1,
            linecolor="grey",
            color="black",
            gridcolor="lightgrey",
            gridwidth=0.5,
            title_text="Date",
            title_font_size=18,
            side="bottom",
            tickfont_size=14,
            tickangle=-45,
            tickformat="%b-%Y",
            automargin=True,
        )
        self._fig.update_yaxes(
            secondary_y=False,
            showline=True,
            linewidth=1,
            linecolor="grey",
            color="black",
            gridcolor="lightgrey",
            gridwidth=0.5,
            title_text="LOC",
            title_font_size=18,
            tickfont_size=14,
            range=[0, None],
            autorange="max",
            rangemode="tozero",
            automargin=True,
            spikethickness=1,
            spikemode="toaxis+across",
        )
        self._fig.update_yaxes(
            secondary_y=True,
            showline=True,
            linewidth=1,
            linecolor="grey",
            color="black",
            gridcolor="lightgrey",
            gridwidth=0.5,
            title_text="Difference of LOC",
            title_font_size=18,
            tickfont_size=14,
            range=[0, None],
            autorange="max",
            rangemode="tozero",
            automargin=True,
            spikethickness=1,
            spikemode="toaxis+across",
            overlaying="y",
            side="right",
        )
        self._fig.update_layout(
            font_family="Open Sans",
            plot_bgcolor="white",
            title={
                "text": f"LOC trend by Language - {sub_title}",
                "x": 0.5,
                "xanchor": "center",
                "font_size": 20,
            },
            xaxis={"dtick": "M1"},
            legend_title_font_size=14,
            legend_font_size=14,
        )
        return self

    def update_xaxis_tickformat(self, interval: str) -> ChartBuilderSelf:
        """
        Update the x-axis tick format based on the interval.

        Args:
            interval (str): The interval to use for formatting the x-axis ticks.
                            Should be one of 'daily', 'weekly', or 'monthly'.

        Returns:
            ChartBuilderSelf: The instance of the ChartBuilder for method chaining.
        """
        tickformat = {
            "daily": "%b %d, %Y",
            "weekly": "%b %d, %Y",
            "monthly": "%b %Y",
        }.get(interval, "%b %d, %Y")

        self._fig.update_xaxes(tickformat=tickformat)
        return self

    def build(
        self,
        trend_data: pd.DataFrame,
        summary_data: pd.DataFrame,
        interval: str,
        sub_title: str,
    ) -> go.Figure:
        """
        Constructs the chart by setting data and creating figure and traces.

        This method configures the chart builder with the given `trend_data` and
        `sum_data`, creates a new figure, then creates and attaches the necessary
        trend and summary line traces, and finally updates the figure layout before
        returning it.

        Parameters:
            trend_data (pd.DataFrame): A pandas DataFrame containing the data to be used for
                                       trend trace creation.
            summary_data (pd.DataFrame): A pandas DataFrame containing the data to be used for
                                     summary trace creation.
            interval (str): The interval to use for formatting the x-axis ticks.
            sub_title (str): The subtitle to be displayed in the chart title.
        Returns:
            ChartBuilderSelf: The Plotly figure object configured with the trend and summary
                              traces, ready for display or further modification.
        """
        self.set_trend_data(trend_data)
        self.set_summary_data(summary_data)
        self.create_fig()
        self.create_trend_trace(xaxis_column=interval)
        self.create_sum_trace(xaxis_column=interval)
        # self.create_diff_trace(xaxis_column=interval)
        self.create_bar_trace(xaxis_column=interval)
        self.update_fig(sub_title)
        self.update_xaxis_tickformat(interval)
        return self._fig

    def show(self) -> None:
        """
        Displays the constructed chart in a browser window.

        This method should be called after the chart has been built using the
        `build` method. It uses the internal figure instance (`_fig`) to render
        the chart using Plotly's default rendering engine.
        """
        self._fig.show()
