from dash import Dash, dcc, html, Input, Output, State, ctx, no_update, DiskcacheManager, CeleryManager
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from copy import deepcopy
from dotenv import load_dotenv
from agent_class import Agent
load_dotenv()

from config import config
from utils import (
    pre_parse_pdf, 
    add_pdf_to_db, 
    get_qdrant_response, 
    get_openai_response,
    detect_language,
)
from dash_utils import create_references_cards
import time
import io
import sys
import re



# if 'REDIS_URL' in os.environ:
# Use Redis & Celery if REDIS_URL set as an env variable
# from celery import Celery
# celery_app = Celery(__name__, broker=os.environ['REDIS_URL'], backend=os.environ['REDIS_URL'])
# background_callback_manager = CeleryManager(celery_app)

# else:
# Diskcache for non-production apps when developing locally
import diskcache
cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)

app = Dash(
    __name__, 
    title='Logos',
    external_stylesheets=[dbc.themes.LITERA]
)
server=app.server

GRAY = '#474747'

title_image = html.Img(
    src='/assets/images/logos.png', 
    style={'width': '300px', 'display': 'block', 'margin-left': 'auto', 'margin-right': 'auto'}
)

navigate_buttons_style = {
    'width': '200px', 
    'display': 'block', 
    'margin-left': 'auto', 
    'margin-right': 'auto',
    'margin-top': '8px',
    'color': GRAY, 
    'background-color': 'white',
    'border-color': 'white', 
    'border-width': '0px',
    'font-size': '1.3rem', 
    'line-height': '1.5', 
    'font-weight': '700',
}

navigate_question = html.Button(
    'Question',
    id='navigate-question',
    style={
        **navigate_buttons_style,
        'border-bottom': f'2px solid {GRAY}',
    }
)

navigate_add = html.Button(
    'Add Document',
    id='navigate-add',
    style=navigate_buttons_style
)

first_row = dbc.Row(
    [
        dbc.Col(navigate_question, width={"size": 2, "offset": 4}),
        dbc.Col(navigate_add, width=2),
    ],
    style={
        'margin-top': '10px',
    }
)

# Question components
text_input = dbc.Textarea(
    id="text-input", 
    placeholder="The unexamined life is not worth living! Ask something...", 
    value="",
    rows=2,
    draggable=False, 
    style={
        'max-width': '600px', 
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': 'auto', 
        'border-color': GRAY,
        'box-shadow': '0px 1px 4px rgb(0 0 0 / 70%)',
        'resize': 'vertical', 
        # 'fontSize': '25px',
    }
)

use_external_search = dbc.Checklist(
    options=[
        # {"label": "Use external search", "value": 1, "disabled": True},
        {"label": "Use expert agent", "value": 1, "disabled": False}
    ],
    value=[],
    id="checklist-inline-input",
    inline=True,
)

# use_external_search_tooltip = dbc.Tooltip(
#     "Use external search is available to premium users.",
#     target="checklist-inline-input",
#     placement="left",
#     style={
#         'font-size': '0.9rem',
#         'color': GRAY,
#     }
# )

# use_expert_agent_tooltip = dbc.Tooltip(
#     "Use external agent to ask more complex questions.",
#     target="checklist-inline-input_1",
#     placement="right",
#     style={
#         'font-size': '0.9rem',
#         'color': GRAY,
#     }
# )

question_button = dbc.Button(
    "Ask", 
    id="button-question", 
    color="primary", 
    style={
        'width': '120px', 
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': 'auto',
        'color': GRAY, 
        'background-color': 'white',
        'border-color': GRAY, 'border-radius': '0.25rem', 'border-width': '2px',
        'font-size': '1.1rem', 'line-height': '1.5', 'font-weight': '400',
    }
)

question_input_components = html.Div(
    id='div-question-input-components',
    children=[
        text_input,
        use_external_search,
        # use_external_search_tooltip, TODO create tooltip for each checkbox
        # use_expert_agent_tooltip,
        question_button,
    ],
    style={
        'width': '600px', 
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': 'auto',
        'margin-top': '8px'
    }
)

answer_text = html.Div(
    children=[],
    id='answer-text',
    style={
        # 'width': '600px', 
        'height': '300px',
        # 'display': 'block', 
        # 'margin-left': 'auto', 
        # 'margin-right': 'auto',
        # 'margin-top': '8px',
        'color': GRAY, 
        'background-color': 'white',
        'border-color': GRAY, 
        'border-radius': '0.25rem', 
        'border-width': '1px',
        'border-style': 'solid',
        'font-size': '1.1rem',
        'box-shadow': '0px 1px 4px rgb(0 0 0 / 70%)',
        'overflow-y': 'scroll',
        'padding': '10px',
    }
)

references_button = dbc.Button(
    "References", 
    id="button-references", 
    color="primary", 
    style={
        'width': '110px', 
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': '0',
        'margin-top': '0px',
        'color': GRAY, 
        'background-color': 'white',
        'border-color': GRAY, 'border-radius': '0.25rem', 'border-width': '1px',
        'font-size': '1rem', 
        'font-weight': '400',
        'padding': '1px',
    }
)

collapsible_references = dbc.Collapse(
    id="collapsible-references",
    is_open=False,
)

expert_agent_logs_button = dbc.Button(
    "Expert agent", 
    id="button-expert-agent-logs", 
    color="primary", 
    style={
        'width': '110px', 
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': '0',
        'margin-top': '0px',
        'color': GRAY, 
        'background-color': 'white',
        'border-color': GRAY, 'border-radius': '0.25rem', 'border-width': '1px',
        'font-size': '1rem', 
        'font-weight': '400',
        'padding': '1px',
    }
)

response_components = html.Div(
    id='div-response-components',
    children=[
        answer_text,
        dbc.Row(
            children=[
                dbc.Col(
                    references_button,
                    width=3,
                ),
                dbc.Col(
                    expert_agent_logs_button,
                    width=3,
                ),
            ],
            justify="end",
            style={
                'margin-top': '0px',
            }
        ),
    ],
    style={
        'width': '600px', 
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': 'auto',
        'margin-top': '8px',
        'display': 'none',
        'visibility': 'hidden',
    }
)

expert_agent_logs_div = html.Div(
    children=[],
    id='div-expert-agent-logs-text',
    style={
        'width': '600px', 
        'height': '300px',
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': 'auto',
        # 'margin-top': '8px',
        'color': 'rgba(100, 100, 100, 0.6)', 
        'background-color': 'white',
        'border-width': '0px',
        'font-size': '1.1rem',
        'box-shadow': '0px 1px 8px rgb(0 0 0 / 20%)',
        'overflow-y': 'scroll',
        'padding': '10px',
    }
)

collapsible_agent_logs = dbc.Collapse(
    id="collapsible-agent-logs",
    is_open=False,
    children=[expert_agent_logs_div],
)

question_component = html.Div(
    children=[
        question_input_components,
        html.Br(),
        response_components,
        collapsible_references,
        collapsible_agent_logs,
    ],
    id='div-question-component',
    style={"visibility": "visible", "display": "block"},
)

# Add components
from_storage = dbc.Row(
    [
        dbc.Label("Integration:", html_for="input-from-storage-row", style={'opacity': '0.4'}, width=3),
        dbc.Col(html.Img(src="/assets/images/gdrive.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
        dbc.Col(html.Img(src="/assets/images/dropbox.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
        dbc.Col(html.Img(src="/assets/images/s3.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
        dbc.Col(html.Img(src="/assets/images/gdocs.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
        dbc.Col(html.Img(src="/assets/images/twitter.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
        dbc.Col(html.Img(src="/assets/images/database.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
        dbc.Col(html.Img(src="/assets/images/slack.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
        dbc.Col(html.Img(src="/assets/images/discord.png", style={'width': '40px', 'height': '40px', 'opacity': '0.4'}), width=1),
    ],
    id="row-load-from-storage",
    className="mb-3",
    style={
        'width': '550px',
        'margin-left': 'auto',
        'margin-right': 'auto',
    }
)

from_url = dbc.Row(
    [
        dbc.Label("From url:", html_for="input-from-url-row", style={'opacity': '0.4'}, width=3),
        dbc.Col(
            dbc.Input(
                type="url", id="input-from-url-row", placeholder="url", disabled=True
            ),
            width=9,
        ),
    ],
    id="row-load-from-url",
    className="mb-3",
    style={
        'width': '550px',
        'margin-left': 'auto',
        'margin-right': 'auto',
    }
)

upload_area = dbc.Row(
    [
        dbc.Label("From file:", html_for="input-from-url-row", width=3),
        dbc.Col( 
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select File')
                ]),
                style={
                    # 'width': '500px',
                    # 'display': 'block', 
                    # 'margin-left': 'auto', 
                    # 'margin-right': 'auto',
                    # 'margin-top': '8px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center'
                },
                multiple=False
            ),
            width=9,
        ),
    ],
    className="mb-3",
    style={
        'width': '550px',
        'margin-left': 'auto',
        'margin-right': 'auto',
    }
)

title_input = dbc.Row(
    [
        dbc.Label("Title", html_for="input-title-row", width=2),
        dbc.Col(
            dbc.Input(
                type="text", id="input-title-row", placeholder="Title"
            ),
            width=10,
        ),
    ],
    className="mb-3",
)

author_input = dbc.Row(
    [
        dbc.Label("Author", html_for="input-author-row", width=2),
        dbc.Col(
            dbc.Input(
                type="text",
                id="input-author-row",
                placeholder="Author name",
            ),
            width=10,
        ),
    ],
    className="mb-3",
)

year_input = dbc.Row(
    [
        dbc.Label("Year", html_for="input-year-row", width=2),
        dbc.Col(
            dbc.Input(
                type="number", min=-1000, max=2023, step=1,
                id="input-year-row",
                placeholder="2000",
            ),
            width=10,
        ),
    ],
    className="mb-3",
)

add_form = dbc.Form(
    children=[
        title_input, 
        author_input, 
        year_input,
    ],
    style={
        'width': '500px',
        'display': 'block',
        'margin-left': 'auto',
        'margin-right': 'auto',
        'margin-top': '8px',
    }
)

add_document_button = dbc.Button(
    "Add document", 
    id="button-add-document", 
    color="primary", 
    style={
        'width': '170px', 
        'display': 'block', 
        'margin-left': 'auto', 
        'margin-right': 'auto',
        'margin-top': '8px',
        'color': GRAY, 
        'background-color': 'white',
        'border-color': GRAY, 'border-radius': '0.25rem', 'border-width': '2px',
        'font-size': '1.1rem', 'line-height': '1.5', 'font-weight': '400',
    }
)

waiting_area_1 = dbc.Row(
    children=[
        # dbc.Col(
        #     html.P("Processing and adding document...", id="txt-waiting", style={"visibility": "hidden"}),
        #     width={"size": 3, "offset": 4},
        #     style={"text-align": "center", "size": "100px"}
        # ),
        dbc.Col(
            html.Img(id="img-waiting", style={"visibility": "hidden", "width": "70px", "height": "70px"}),
            width={"size": 1, "offset": 6},
        ),
    ]
)

add_component = html.Div(
    children=[
        from_storage,
        dbc.Tooltip(
            "Integration with external storage is available to premium users.",
            target="row-load-from-storage",
            placement="left",
            style={
                'font-size': '0.9rem',
                'color': GRAY,
            }
        ),
        from_url,
        dbc.Tooltip(
            "URL parsing is available to premium users.",
            target="row-load-from-url",
            placement="left",
            style={
                'font-size': '0.9rem',
                'color': GRAY,
            }
        ),
        upload_area,
        html.Br(),
        add_form,
        add_document_button,
        html.Br(),
        waiting_area_1,
    ],
    id='div-add-component',
    style={"visibility": "hidden", "display": "none"}
)

# App layout
add_document_toast = dbc.Toast(
    "",
    id="add-document-toast",
    is_open=False,
    dismissable=True,
    duration=10000,
    icon="primary",
    style={"position": "fixed", "top": 66, "right": 10, "width": 350},
)

app.layout = html.Div(
    children=[
        title_image,
        add_document_toast,
        first_row,
        html.Br(),
        html.Br(),
        html.Div(
            id='div-page-content',
            children=[
                question_component,
                add_component
            ],
        ),
        html.Br(),
        html.Br(),
        dcc.Interval(
            id='interval-component',
            interval=0.3*1000, # in milliseconds
            n_intervals=0,
            max_intervals=0
        ),
        dcc.Store(id='logs-store'),
    ]
)


# Callback  to show expert agent logs
@app.callback(
    Output('div-expert-agent-logs-text', 'children'),
    Input('interval-component', 'n_intervals'),
    State('logs-store', 'data')
)
def update_logs(n, data):
    if n <= 0:
        return no_update
    cleaned_logs = re.sub(r'\x1b[^m]*m', '', data)
    splited_logs = cleaned_logs.split('\n')

    output_components = [
        html.P('Expert agent thought process:', style={'font-weight': 'bold'})
    ]
    counter = 0
    for e in splited_logs:
        if 'Action:' in e or 'Action Input:' in e or 'Finished chain' in e:
            continue
        if 'Observation:' in e or 'Thought:' in e or 'Answer:' in e:
            splited_sentence = e.split(':')
            action = splited_sentence[0]
            answer = splited_sentence[1]
            if not answer:
                continue
            output_component = html.P([
                html.Span(
                        children=f'{action.strip()}: ',
                        style={'font-weight': 'bold'}
                    ),
                html.Span(children=answer)
            ])
            output_components.append(output_component)
            counter += 1
            continue

        if counter == 0 and e:
            output_component = html.P([
                html.Span(
                        children=f'Thought: ',
                        style={'font-weight': 'bold'}
                    ),
                html.Span(children=e)
            ])
            output_components.append(output_component)
            counter += 1
            continue
        
        output_component = html.P(
            html.Span(e)
        )
        output_components.append(output_component)
        counter += 1

    return html.Div(output_components)


# Callbacks Question
@app.callback(
    Output("collapsible-references", "is_open"),
    [Input("button-references", "n_clicks")],
    [State("collapsible-references", "is_open")],
)
def toggle_collapse_references(n, is_open):
    if n:
        return not is_open
    return is_open


@app.callback(
    Output("collapsible-agent-logs", "is_open"),
    Input("button-expert-agent-logs", "n_clicks"),
    Input('button-question', 'n_clicks'),
    State("collapsible-agent-logs", "is_open"),
    State("checklist-inline-input", "value"),
)
def toggle_collapse_references(n_show, n_ask, is_open, checklist_value):
    if n_show:
        return not is_open
    if n_ask and checklist_value == [1]:
        return True
    return is_open


# Callbacks Add document
@app.callback(
    Output('div-add-component', 'style'),
    Output('div-question-component', 'style'),
    Output('navigate-question', 'style'),
    Output('navigate-add', 'style'),
    Input('navigate-question', 'n_clicks'),
    Input('navigate-add', 'n_clicks'),
    State('div-add-component', 'style'),
    State('div-question-component', 'style'),
)
def display_page(n_clicks_question, n_clicks_add, add_style, question_style):
    button_id = ctx.triggered_id
    selected_style = deepcopy(navigate_buttons_style)
    selected_style['border-bottom'] = f'2px solid {GRAY}'
    unselected_style = deepcopy(navigate_buttons_style)
    unselected_style['border-bottom'] = f'0px white'
    if button_id is None:
        return no_update, no_update, no_update, no_update
    elif button_id == 'navigate-question':
        add_style.update({'visibility': 'hidden', 'display': 'none'})
        question_style.update({'visibility': 'visible', 'display': 'block'})
        return add_style, question_style, selected_style, unselected_style
    elif button_id == 'navigate-add':
        question_style.update({'visibility': 'hidden', 'display': 'none'})
        add_style.update({'visibility': 'visible', 'display': 'block'})
        return add_style, question_style, unselected_style, selected_style


@app.callback(
    Output('input-title-row', 'value'),
    Output('input-author-row', 'value'),
    Output('input-year-row', 'value'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('upload-data', 'last_modified')
)
def update_forms(file_contents, file_name, last_modified):
    if file_contents is not None:    
        metadata = pre_parse_pdf(base64_pdf_bytestring=file_contents, use_openai=True)
        return metadata['title'], metadata['author'], metadata['year']
    return "", "", ""


@app.callback(
    Output('add-document-toast', 'children'),
    Output('add-document-toast', 'is_open'),
    Output('add-document-toast', 'icon'),
    Input('button-add-document', 'n_clicks'),
    State('upload-data', 'contents'),
    State('input-title-row', 'value'),
    State('input-author-row', 'value'),
    State('input-year-row', 'value'),
    background=True,
    manager=background_callback_manager,
    running=[
        (Output("button-add-document", "disabled"), True, False),
        (Output("img-waiting", "style"), {"visibility": "visible", "width": "70px", "height": "70px"}, {"visibility": "hidden"}),
        (Output("img-waiting", "src"), "assets/images/book.gif", None)
    ],
    prevent_initial_call=True,
)
def add_document(n_clicks, file_contents, title, author, year):
    if n_clicks is not None:
        if file_contents is not None and title is not None and author is not None and year is not None:
            result = add_pdf_to_db(
                base64_pdf_bytestring=file_contents,
                title=title,
                author=author,
                year=year
            )
            if result == "success":
                return "Document added successfully!", True, "primary"
            else:
                return "Error adding document!", True, "danger"
        else:
            return "Missing document or information!", True, "danger"
    return no_update, no_update, no_update


# Callback ask question
@app.callback(
    Output("answer-text", "children"),
    Output("collapsible-references", "children"),
    Output("div-response-components", "style"),
    Output('interval-component', 'max_intervals'),
    Output('logs-store', 'data'),
    Input('button-question', 'n_clicks'),
    State('text-input', 'value'),
    State("checklist-inline-input", "value"),
    State("div-response-components", "style"),
    progress=[
        Output('logs-store', 'data'),
        Output('interval-component', 'max_intervals'),
    ],
    manager=background_callback_manager,
    running=[
        (Output("button-question", "children"), dbc.Spinner(size="sm"), "Ask"),
        (Output("button-question", "disabled"), True, False),
    ],
    prevent_initial_call=True,
    background=True
)
def send_question(set_progress, n_clicks, question, checklist_value, response_components_style):
    if not n_clicks:
        raise PreventUpdate()

    # Detect question language
    language = detect_language(question, module="python")

    # If user selects the expert agent search
    if checklist_value == [1]:
        agent = Agent()
        agent.language = language
        agent.ask_expert_agent(question)

        output_buffer = io.StringIO()
        sys.stdout = sys.stderr = output_buffer
        while agent.run_in_background_thread.is_alive():
            logs = output_buffer.getvalue()
            set_progress((str(logs), -1))
            time.sleep(2)
        logs = output_buffer.getvalue()
        set_progress((str(logs), -1))
        sys.stdout = sys.__stdout__
        time.sleep(1) # This will ensure that the logs are printed before the answer

        agent_answer = agent.run_in_background_queue.get()
        references_rows = create_references_cards(references=agent.qdrant_answers)
        answer_text = html.P(str(agent_answer))
        updated_style = deepcopy(response_components_style)
        updated_style['visibility'] = 'visible'
        updated_style['display'] = 'block'
        return answer_text, references_rows, updated_style, 0, str(logs)
    
    # If simple semantic search
    else:
        qdrant_answer = get_qdrant_response(question)
        prompt = ""
        for r in qdrant_answer:
            prompt += f"""excerpt: author: {r.payload.get('author')}, title: {r.payload.get('title')}, text: {r.payload.get('text')}\n"""
        
        if len(prompt) > 9000:
            prompt = prompt[0:9000]

        prompt += f"""
Given the excerpts above, answer the following question in {language}:
Question: {question}"""

        openai_answer = get_openai_response(prompt=prompt)
        if not openai_answer or not openai_answer.choices:
            return "No answer found"
        
        references_rows = create_references_cards(references=qdrant_answer)
        answer_text = html.P(str(openai_answer.choices[0].message.content))

    updated_style = deepcopy(response_components_style)
    updated_style['visibility'] = 'visible'
    updated_style['display'] = 'block'
    return answer_text, references_rows, updated_style, 0, ''


if __name__ == '__main__':
    app.run_server(
        debug=False, #config.DEBUG,
        host=config.HOST,
        port=config.PORT,
        dev_tools_ui=None, 
        dev_tools_props_check=None, 
        dev_tools_serve_dev_bundles=None, 
        dev_tools_hot_reload=None, 
        dev_tools_hot_reload_interval=None, 
        dev_tools_hot_reload_watch_interval=None, 
        dev_tools_hot_reload_max_retry=None, 
        dev_tools_silence_routes_logging=None, 
        dev_tools_prune_errors=None
    )