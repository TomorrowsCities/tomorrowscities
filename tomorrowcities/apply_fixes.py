with open('pages/engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. ChartCard
old_chart_card = '''@solara.component
def ChartCard(option):
    with solara.Card(
        elevation=1,
        style={
            "padding": "8px",
            "borderRadius": "14px",
            "border": "1px solid rgba(31, 42, 51, 0.08)",
            "background": "#fcfdff",
        },
    ):
        solara.FigureEcharts(option=option, attributes={"style": "height:340px; width:100%;"})'''

new_chart_card = '''@solara.component
def ChartCard(option):
    with solara.Card(
        elevation=1,
        style={
            "padding": "4px",
            "borderRadius": "14px",
            "border": "1px solid rgba(31, 42, 51, 0.08)",
            "background": "#fcfdff",
            "overflow": "hidden",
            "width": "100%",
            "maxWidth": "100%",
        },
    ):
        with solara.Column(style={"padding": "0", "margin": "0", "width": "100%", "maxWidth": "100%", "overflow": "hidden"}):
            solara.FigureEcharts(option=option, attributes={"style": "height:340px; width:100%; max-width:100%; overflow:hidden;"})'''

if old_chart_card in text:
    text = text.replace(old_chart_card, new_chart_card)
    print('ChartCard replaced')
else:
    print('ChartCard not found')

# 2. GeneratedDataTablesCharts GridFixed
old_grid = 'with solara.GridFixed(columns=2):'
new_row = 'with solara.Row(classes=["responsive-chart-container"]):'
if old_grid in text:
    text = text.replace(old_grid, new_row)
    print('GridFixed replaced')
else:
    print('GridFixed not found')

# 3. GeneratedDataTablesCharts CSS
old_b_none = '''    if buildings is None:
        solara.Info("There is no generated exposure data yet.")
        return'''
        
new_css = '''    if buildings is None:
        solara.Info("There is no generated exposure data yet.")
        return

    solara.Style(\"\"\"
        .responsive-chart-container {
            display: flex !important;
            flex-wrap: wrap !important;
            gap: 16px !important;
            width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        .responsive-chart-container > div {
            flex: 0 0 calc(50% - 8px) !important;
            max-width: calc(50% - 8px) !important;
            min-width: 0 !important;
            margin: 0 !important;
            box-sizing: border-box !important;
        }
        @media (max-width: 768px) {
            .responsive-chart-container > div {
                flex: 0 0 100% !important;
                max-width: 100% !important;
                min-width: 100% !important;
            }
        }
    \"\"\")'''
if old_b_none in text:
    text = text.replace(old_b_none, new_css, 1) # Only first occurrence
    print('CSS injected')
else:
    print('CSS target not found')

# 4. LayerDisplayer Tabs
old_layer_disp = '''    solara.ToggleButtonsSingle(value=selected, on_value=set_selected,
                               values=nonempty_layer_names)'''
                               
new_layer_disp = '''    solara.Style(\"\"\"
        .scrollable-tabs {
            width: 100% !important;
            max-width: 100vw !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
            padding-bottom: 4px;
        }
        .layer-table-wrapper {
            width: 100% !important;
            overflow-x: auto !important;
        }
        .scrollable-tabs > div {
            display: inline-flex !important;
            flex-wrap: nowrap !important;
        }
    \"\"\")
    with solara.Row(classes=["scrollable-tabs"]):
        solara.ToggleButtonsSingle(value=selected, on_value=set_selected,
                                   values=nonempty_layer_names)'''
                                   
if old_layer_disp in text:
    text = text.replace(old_layer_disp, new_layer_disp)
    print('LayerDisplayer replaced')
else:
    print('LayerDisplayer not found')

with open('pages/engine.py', 'w', encoding='utf-8') as f:
    f.write(text)
