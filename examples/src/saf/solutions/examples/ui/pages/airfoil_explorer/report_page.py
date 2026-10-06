import dash
from dash import html

dash.register_page(
    __name__,
    name="Report",
    path_template="/projects/<project_id>/airfoil-explorer/report",
)


#TODO replace with actual content for the Report page
layout = html.Div("Airfoil Explorer Report")