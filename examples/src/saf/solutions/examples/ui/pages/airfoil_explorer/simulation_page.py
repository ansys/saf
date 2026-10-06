import dash
from dash import html

dash.register_page(
    __name__,
    name="Simulation",
    path_template="/projects/<project_id>/airfoil-explorer/simulation",
)


#TODO replace with actual content for the Simulation page
layout = html.Div("Airfoil Explorer Simulation")