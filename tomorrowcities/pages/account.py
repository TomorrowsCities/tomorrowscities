from typing import Optional
import solara
import os
import pprint
from urllib.parse import parse_qs
import json

from . import user, User, login_failed, config, LoginForm, \
              github_client, google_client, \
              session_storage, read_from_session_storage, store_in_session_storage


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
        solara.Text(f'Hello {user.value.username}')
        if user.value.user_profile:
            for key, value in user.value.user_profile.items():
                if key in ['avatar_url', 'picture']:
                    solara.Image(value)
                else:
                    solara.Text(f'{key}: {value}')

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
            user.value = User(username, admin=False, user_profile=user_dict)
            
            login_failed.value = False

            store_in_session_storage('user', user.value)
           
            # used only to force updating of the page
            force_update_counter.value += 1
            router.push('/account')




