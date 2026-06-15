with open('pages/engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_metrics_tabs = '''    with solara.lab.Tabs():
        with solara.lab.Tab("Boxplot"):
            with solara.GridFixed(columns=1):
                solara.FigureEcharts(option=options, attributes={"style": "height:400%; width:100%"})
        with solara.lab.Tab("Data"): 
            solara.DataFrame(df)
        with solara.lab.Tab("Stats"): 
            solara.DataFrame(summary.reset_index())'''

new_metrics_tabs = '''    with solara.lab.Tabs():
        with solara.lab.Tab("Boxplot"):
            with solara.GridFixed(columns=1):
                solara.FigureEcharts(option=options, attributes={"style": "height:520px; width:100%"})
        with solara.lab.Tab("Data"): 
            with solara.Row(justify="end", style={"margin-bottom": "8px", "padding-right": "8px", "margin-top": "8px"}):
                solara.FileDownload(data=lambda: df.to_csv(index=False), filename="Metric_Data.csv", label="Export CSV")
            solara.DataFrame(df)
        with solara.lab.Tab("Stats"): 
            stats_df = summary.reset_index().rename(columns={'index': 'Statistic'})
            with solara.Row(justify="end", style={"margin-bottom": "8px", "padding-right": "8px", "margin-top": "8px"}):
                solara.FileDownload(data=lambda: stats_df.to_csv(index=False), filename="Metric_Stats.csv", label="Export CSV")
            solara.DataFrame(stats_df)'''

if old_metrics_tabs in text:
    text = text.replace(old_metrics_tabs, new_metrics_tabs)
    print("MetricStatistics replaced")
else:
    print("MetricStatistics not found")

with open('pages/engine.py', 'w', encoding='utf-8') as f:
    f.write(text)
