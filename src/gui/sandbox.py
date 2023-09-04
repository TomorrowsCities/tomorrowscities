import solara
import ipyleaflet
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import math
import numpy as np

plt.switch_backend("agg")

@solara.component
def DialWidget(desc, value, max_value=10000):
    if max_value == 0:
        max_value = 10000
    fig = Figure(tight_layout=True,dpi=30,frameon=False)
    fig.set_size_inches(1.5,1)
    ax = fig.subplots()
    ax.axis('equal')
    ax.axis('off')

    ax.set_xticks([])
    ax.set_yticks([])

    t = np.linspace(0, math.pi, 100)

    cos = np.cos(t)
    sin = np.sin(t)

    ax.plot(cos,sin, linewidth=2)
    value_t = math.pi * (1 - (value / max_value))

    fill_color = 'red'
    if value_t >  math.pi / 2  :
        x1 = np.linspace(-1,np.cos(value_t),100)
        y1 = np.sqrt(1 - x1**2)
        ax.fill_between(x1,y1,color=fill_color)
        x1 = np.linspace(np.cos(value_t),0,100)
        y1 = np.tan(value_t) * x1
        ax.fill_between(x1,y1,color=fill_color)
    else:
        x = np.linspace(-1, np.cos(value_t),100)
        y1 = np.sqrt(1-x**2)
        y2a = np.zeros(100)
        y2b = np.tan(value_t) * x
        y2 = np.maximum(y2a,y2b)
        ax.fill_between(x,y1,y2,color=fill_color)

    #ax.plot([0,0.9*np.cos(value_t)],[0, 0.9*np.sin(value_t)], linewidth=10)
    #ax.scatter([0],[0],color='black',s=50)
    #ax.text(-1.1,0,0,fontdict={'fontsize':14},verticalalignment="center",
    #    horizontalalignment="right",color="black")
    #ax.text(1.1,0,max_value,fontdict={'fontsize':14},verticalalignment="center",
    #    horizontalalignment="left",color="black")
    #ax.plot([-0.9,-1.1],[0,0],color="black")
    #ax.plot([0.9,1.1],[0,0],color="black")
    #ax.plot([0,0],[0.9,1.1],color="black")
    horizontalalignment = "right" if value_t > math.pi/2 else "left"
    #ax.text(1.1*np.cos(value_t),1.1*np.sin(value_t),value,fontdict={'fontsize':20},verticalalignment="center",
    #    horizontalalignment=horizontalalignment,color="black")
    ax.text(0,0.5,value,fontdict={'fontsize':20},verticalalignment="center",
        horizontalalignment="center",color="black")
    ax.set_xlim(-1.1,1.1)
    ax.set_ylim(-0.2,1.2)
    #ax.text(0, -0.1, desc,fontdict={'fontsize':20},verticalalignment="center",
    #    horizontalalignment='center',color="white")
    solara.FigureMatplotlib(fig)

metrics_template = {"metric1": {"desc": "Number of workers unemployed", "value": 0, "max_value": 0},
        "metric2": {"desc": "Number of children with no access to education", "value": 0, "max_value": 0},
        "metric3": {"desc": "Number of households with no access to hospital", "value": 0, "max_value": 0},
        "metric4": {"desc": "Number of individuals with no access to hospital", "value": 0, "max_value": 0},
        "metric5": {"desc": "Number of homeless households", "value": 0, "max_value": 0},
        "metric6": {"desc": "Number of homeless individuals", "value": 0, "max_value": 0},
        "metric7": {"desc": "Population displacement", "value": 0, "max_value": 0},}

metrics = solara.reactive(metrics_template)

def generate_metrics():
    
    new_metrics = metrics_template.copy()
    for m in new_metrics.keys():
        max_value = np.random.randint(500, 10001)
        value = int(np.random.random() * max_value)
        new_metrics[m]["max_value"] = max_value
        new_metrics[m]["value"] = value

    metrics.set(new_metrics)
    
@solara.component
def Page(): 




    solara.Button(label="Generate", on_click=generate_metrics)
    
    for name, metric in metrics.value.items():
        DialWidget(name, metric["value"], max_value=metric["max_value"])


Page()
