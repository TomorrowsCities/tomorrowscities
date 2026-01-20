from typing import Optional
import solara
from solara.alias import rv
import os
import pprint
from urllib.parse import parse_qs
import json

from . import user, User, config, LoginForm, \
              github_client, google_client, \
              session_storage, read_from_session_storage, store_in_session_storage, \
              logout


# used only to force updating of the page
force_update_counter = solara.reactive(0)

def is_callback(router):
    if router.search is not None:
        params = parse_qs(router.search)
        if set({'code','state'}).issubset(set(params.keys())):
            return True
    return False


@solara.component
def Page():
    solara.Title(" ")

    if user.value is None:
        LoginForm()        
    else:
        profile = user.value.user_profile or {}
        avatar = profile.get('avatar_url') or profile.get('picture')
        name = profile.get('name', user.value.username)
        email = profile.get('email', '')
        
        with solara.Card(style={"max-width": "400px", "margin": "0 auto", "padding": "20px"}):
            with solara.Column(align="center"):
                if avatar:
                    rv.Img(src=avatar, height="100", width="100", style_="border-radius: 50%; margin-bottom: 15px")
                
                solara.Text(name, style={"font-size": "1.5rem", "font-weight": "bold"})
                if email:
                    solara.Text(email, style={"color": "gray", "margin-bottom": "20px"})
                
                solara.Markdown("---")
                
                with solara.GridFixed(columns=2, row_gap="10px"):
                    if 'given_name' in profile:
                        solara.Text("First Name:", style={"font-weight": "bold"})
                        solara.Text(profile['given_name'])
                    if 'family_name' in profile:
                        solara.Text("Last Name:", style={"font-weight": "bold"})
                        solara.Text(profile['family_name'])
                    if 'locale' in profile:
                        solara.Text("Locale:", style={"font-weight": "bold"})
                        solara.Text(profile['locale'])
                    
                    solara.Text("Company:", style={"font-weight": "bold"})
                    solara.Text(user.value.auth_company or "Local")
                
                solara.Markdown("---")
                solara.Button("Logout", color="red", on_click=logout, width="100%", style={"margin-top": "20px"})

    router = solara.use_router()
    if is_callback(router):
        print('entering callback')
        # callback is made
        if router.search is not None:
            params = parse_qs(router.search)
            print('callback is made',params)
            code = params['code'][0]
            state = params['state'][0]

            auth_company = read_from_session_storage('auth_company')
            state_in_session = read_from_session_storage(f'{auth_company}_state')
            
            # Silently ignore state mismatch
            # TODO: display a warning message
            if state_in_session != state:
                return
            redirect_response = config['root_url'] + '/' +router.path+'?'+router.search
            if auth_company == 'github':
                client = github_client
            elif auth_company == 'google':
                client = google_client
            else:
                client = None
            
            client.fetch_token(config[f'{auth_company}_token_url'], 
                    client_secret=config[f'{auth_company}_client_secret'],
                    authorization_response=redirect_response)

            r = client.get(config[f'{auth_company}_user_api'])
            user_dict = json.loads(r.content.decode('utf-8'))
            print(user_dict)
            username = user_dict['name']
            user.value = User(username, admin=False, auth_company=auth_company, user_profile=user_dict)
            
            store_in_session_storage('user', user.value)
           
            # used only to force updating of the page
            force_update_counter.value += 1
            router.push('/account')




