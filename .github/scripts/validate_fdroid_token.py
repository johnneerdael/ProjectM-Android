"""Read-only GitLab permission checks; never output credentials or token response bodies."""
import argparse
import datetime
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


def validate(fork, api):
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',fork):raise ValueError('Invalid GitLab fork')
    token=api('personal_access_tokens/self')
    if not token.get('active') or token.get('revoked'):raise ValueError('GitLab token is inactive or revoked')
    if 'api' not in token.get('scopes',[]):raise ValueError('Synchronization needs the api scope, not read_api/write_repository alone')
    expires=token.get('expires_at')
    if expires and datetime.date.fromisoformat(expires)<=datetime.datetime.now(datetime.timezone.utc).date():raise ValueError('GitLab token has expired')
    project=api('projects/'+urllib.parse.quote(fork,safe=''))
    if project.get('path_with_namespace')!=fork or project.get('archived'):raise ValueError('Fork identity is wrong or archived')
    permissions=project.get('permissions',{})
    role=max((permissions.get(k) or {}).get('access_level',0) for k in ('project_access','group_access'))
    if role<30:raise ValueError('Token needs at least Developer access to the fdroiddata fork')
    branch=api(f"projects/{project['id']}/repository/branches/nl.neerdael.projectmtv")
    if not branch.get('can_push'):raise ValueError('Token cannot push the TV submission source branch')
    mr=api('projects/fdroid%2Ffdroiddata/merge_requests/50236')
    if mr.get('source_project_id')!=project['id'] or mr.get('source_branch')!='nl.neerdael.projectmtv':raise ValueError('Existing TV merge request does not match the fork')
    return {'fork':fork,'api_scope':True,'access_level':role,'branch_can_push':True,'branch_protected':bool(branch.get('protected')),'token_expires_at':expires,'tv_mr_state':mr.get('state')}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fork',default='johnneerdael/fdroiddata');args=parser.parse_args()
    credential=os.environ.get('FDROID_GITLAB_TOKEN','')
    if not credential:raise SystemExit('FDROID_GITLAB_TOKEN is missing')
    opener=urllib.request.build_opener(NoRedirect())
    def api(endpoint):
        request=urllib.request.Request('https://gitlab.com/api/v4/'+endpoint,headers={'PRIVATE-TOKEN':credential,'Accept':'application/json'})
        try:
            with opener.open(request,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as error:raise ValueError(f'GitLab permission check failed with HTTP {error.code}') from None
        except urllib.error.URLError:raise ValueError('GitLab permission check could not reach the API') from None
    try:print(json.dumps(validate(args.fork,api),sort_keys=True))
    except ValueError as error:raise SystemExit(str(error)) from None


if __name__=='__main__':main()
