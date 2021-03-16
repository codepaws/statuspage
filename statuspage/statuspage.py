# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

import sys, os
import hashlib
import base64
from datetime import datetime, timedelta
import requests
from requests.exceptions import ConnectionError
from github import Github, UnknownObjectException, GithubException
import click
from jinja2 import Template
from tqdm import tqdm
from collections import OrderedDict
import markdown2
import json

__version__ = "1.0"

ROOT = os.path.dirname(os.path.realpath(__file__))

PY3 = sys.version_info >= (3, 0)

DEFAULT_CONFIG = {
    "footer": "Status page hosted by GitHub, generated with <a href='https://github.com/jayfk/statuspage'>jayfk/statuspage</a>",
    "logo": "https://raw.githubusercontent.com/jayfk/statuspage/master/template/logo.png",
    "title": "Status",
    "favicon": "https://raw.githubusercontent.com/jayfk/statuspage/master/template/favicon.png",
    "system-color": "171717",
    "status-labels": {
        "investigating": "1192FC",
        "degraded performance":"FFA500",
        "major outage": "FF4D4D"
    },
    "templates": [
        "template.html",
        "style.css",
        "statuspage.js",
        "translations.ini"
    ]
}

@click.group()
@click.version_option(__version__, '-v', '--version')
def cli():  # pragma: no cover
    pass


@cli.command()
def config_init():
    init_default_config()


@cli.command()
@click.option('--name', prompt='Name', help='')
@click.option('--token', prompt='GitHub API Token', help='')
@click.option('--org', help='GitHub Organization', default=False)
@click.option('--systems', prompt='Systems, eg (Website,API)', help='')
@click.option('--private/--public', default=False)
@click.option('--config', help='')
@click.option('--branch-main', help='GitHub main branch', default='main')
@click.option('--branch-pages', help='GitHub pages branch', default='gh-pages')
@click.option('--github-api', help='API server to use', default='https://api.github.com')
@click.option('--ssl-verify', help='Verify SSL on GitHub requests', default=True)
def create(token, name, systems, org, private, config, branch_main, branch_pages, github_api, ssl_verify):
    run_create(name=name, token=token, systems=systems, org=org, private=private, config_path=config, branch_main=branch_main, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)


@cli.command()
@click.option('--name', prompt='Name', help='')
@click.option('--org', help='GitHub Organization', default=False)
@click.option('--token', prompt='GitHub API Token', help='')
@click.option('--branch-pages', help='GitHub pages branch', default='gh-pages')
@click.option('--github-api', help='API server to use', default='https://api.github.com')
@click.option('--ssl-verify', help='Verify SSL on GitHub requests', default=True)
def update(name, token, org, branch_pages, github_api, ssl_verify):
    run_update(name=name, token=token, org=org, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)


@cli.command()
@click.option('--name', prompt='Name', help='')
@click.option('--org', help='GitHub Organization', default=False)
@click.option('--token', prompt='GitHub API Token', help='')
@click.option('--branch-pages', help='GitHub pages branch', default='gh-pages')
@click.option('--github-api', help='API server to use', default='https://api.github.com')
@click.option('--ssl-verify', help='Verify SSL on GitHub requests', default=True)
def upgrade(name, token, org, branch_pages, github_api, ssl_verify):
    run_upgrade(name=name, token=token, org=org, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)


@cli.command()
@click.option('--name', prompt='Name', help='')
@click.option('--org', help='GitHub Organization', default=False)
@click.option('--token', prompt='GitHub API Token', help='')
@click.option('--system', prompt='System', help='System to add')
@click.option('--prompt/--no-prompt', default=True)
@click.option('--branch-pages', help='GitHub pages branch', default='gh-pages')
@click.option('--github-api', help='API server to use', default='https://api.github.com')
@click.option('--ssl-verify', help='Verify SSL on GitHub requests', default=True)
def add_system(name, token, org, system, prompt, branch_pages, github_api, ssl_verify):
    run_add_system(name=name, token=token, org=org, system=system, prompt=prompt, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)


@cli.command()
@click.option('--name', prompt='Name', help='')
@click.option('--org', help='GitHub Organization', default=False)
@click.option('--token', prompt='GitHub API Token', help='')
@click.option('--system', prompt='System', help='System to remove')
@click.option('--prompt/--no-prompt', default=True)
@click.option('--branch-pages', help='GitHub pages branch', default='gh-pages')
@click.option('--github-api', help='API server to use', default='https://api.github.com')
@click.option('--ssl-verify', help='Verify SSL on GitHub requests', default=True)
def remove_system(name, token, org, system, prompt, branch_pages, github_api, ssl_verify):
    run_remove_system(name=name, token=token, org=org, system=system, prompt=prompt, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)


def init_default_config():
    """
    Touches a new config file in the current path
    """
    f = open("config.json", "w")
    f.write(json.dumps(DEFAULT_CONFIG, indent=4, sort_keys=True))
    f.close()
    click.secho("Successfully created new config", fg="green")

def read_local_config(path):
    """
    Reads in a JSON config file from the given path
    """
    if os.path.isfile(path):
        f = open("config.json", "r", encoding='utf-8')
        return json.loads(f.read())
    else:
        raise

def run_add_system(name, token, org, system, prompt, branch_pages, github_api, ssl_verify):
    """
    Adds a new system to the repo.
    """
    repo = get_repo(token=token, org=org, name=name, github_api=github_api, ssl_verify=ssl_verify)
    config = get_config(repo, branch_pages)
    try:
        repo.create_label(name=system.strip(), color=config['system-color'])
        click.secho("Successfully added new system {}".format(system), fg="green")
        if prompt and click.confirm("Run update to re-generate the page?"):
            run_update(name=name, token=token, org=org, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)
    except GithubException as e:
        if e.status == 422:
            click.secho(
                "Unable to add new system {}, it already exists.".format(system), fg="yellow")
            return
        raise


def run_remove_system(name, token, org, system, prompt, branch_pages, github_api, ssl_verify):
    """
    Removes a system from the repo.
    """
    repo = get_repo(token=token, org=org, name=name, github_api=github_api, ssl_verify=ssl_verify)
    try:
        label = repo.get_label(name=system.strip())
        label.delete()
        click.secho("Successfully deleted {}".format(system), fg="green")
        if prompt and click.confirm("Run update to re-generate the page?"):
            run_update(name=name, token=token, org=org, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)
    except UnknownObjectException:
        click.secho("Unable to remove system {}, it does not exist.".format(system), fg="yellow")


def run_upgrade(name, token, org, branch_pages, github_api, ssl_verify):
    click.echo("Upgrading...")

    repo = get_repo(token=token, name=name, org=org, github_api=github_api, ssl_verify=ssl_verify)
    files = get_files(repo=repo)
    head_sha = repo.get_git_ref("heads/" + branch_pages).object.sha

    # add all the template files to the gh-pages branch
    for template in tqdm(DEFAULT_CONFIG['templates'], desc="Updating template files"):
        with open(os.path.join(ROOT, "template", template), "r", encoding='utf-8') as f:
            content = f.read()
            if template in files:
                repo_template = repo.get_contents(
                    path="/" + template,
                    ref=head_sha,
                )
                if not is_same_content(
                    content,
                    base64.b64decode(repo_template.content)
                ):
                    repo.update_file(
                        path=template,
                        sha=repo_template.sha,
                        message="upgrade",
                        content=content,
                        branch=branch_pages
                    )
            else:
                repo.create_file(
                    path=template,
                    message="upgrade",
                    content=content,
                    branch=branch_pages
                )


def run_update(name, token, org, branch_pages, github_api, ssl_verify):
    click.echo("Generating..")
    repo = get_repo(token=token, name=name, org=org, github_api=github_api, ssl_verify=ssl_verify)
    issues = get_issues(repo)

    # get the SHA of the current HEAD
    sha = repo.get_git_ref("heads/" + branch_pages).object.sha

    # get the template from the repo
    template_file = repo.get_contents(
        path="/template.html",
        ref=sha
    )

    # check if the custom config exists, default back to defaults if it does not 
    config = get_config(repo, branch_pages)

    systems = get_systems(repo, issues, config['system-color'], config['status-labels'])
    incidents = get_incidents(repo, issues, config['system-color'], config['status-labels'])
    panels = get_panels(systems)

    # render the template
    template = Template(template_file.decoded_content.decode("utf-8"))
    content = template.render({
        "systems": systems, "incidents": incidents, "panels": panels, "config": config
    })

    # create/update the index.html with the template
    try:
        # get the index.html file, we need the sha to update it
        index = repo.get_contents(
            path="/index.html",
            ref=sha,
        )

        if is_same_content(content, base64.b64decode(index.content)):
            click.echo("Local status matches remote status, no need to commit.")
            return False

        repo.update_file(
            path="index.html",
            sha=index.sha,
            message="update index",
            content=content,
            branch="gh-pages"
        )
    except UnknownObjectException:
        # index.html does not exist, create it
        repo.create_file(
            path="index.html",
            message="initial",
            content=content,
            branch="gh-pages",
        )


def run_create(name, token, systems, org, private, config_path, branch_main, branch_pages, github_api, ssl_verify):
    gh = Github(login_or_token=token, base_url=github_api, verify=ssl_verify)
    config = read_local_config(config_path) if config_path else DEFAULT_CONFIG

    if org:
        entity = gh.get_organization(org)
    else:
        entity = gh.get_user()

    description="Visit this site at https://{login}.github.io/{name}/".format(
        login=entity.login,
        name=name
    )

    # create the repo
    repo = entity.create_repo(name=name, description=description, private=private)

    # get all labels an delete them
    for label in tqdm(list(repo.get_labels()), "Deleting initial labels"):
        label.delete()
    
    # create new status labels
    for label, color in tqdm(config['status-labels'].items(), desc="Creating status labels"):
        repo.create_label(name=label, color=color)
    
    # create system labels
    for label in tqdm(systems.split(","), desc="Creating system labels"):
        repo.create_label(name=label.strip(), color=config['system-color'])

    # add an empty file to main, otherwise we won't be able to create the gh-pages
    # branch
    repo.create_file(
        path="README.md",
        message="initial",
        content=description,
    )

    # create the gh-pages branch
    ref = repo.get_git_ref("heads/" + branch_main)
    repo.create_git_ref(ref="refs/heads/" + branch_pages, sha=ref.object.sha)

    # add all the template files to the gh-pages branch
    for template in tqdm(config['templates'], desc="Adding template files"):
        with open(os.path.join(ROOT, "template", template), "r", encoding='utf-8') as f:
            repo.create_file(
                path=template,
                message="initial",
                content=f.read(),
                branch=branch_pages
            )

    # create an initial config.json file
    repo.create_file(
        path='config.json',
        message="initial",
        content=json.dumps(config, indent=4, sort_keys=True),
        branch=branch_pages
    )

    # set the gh-pages branch to be the default branch
    repo.edit(name=name, default_branch=branch_pages)

    # run an initial update to add content to the index
    run_update(token=token, name=name, org=org, branch_pages=branch_pages, github_api=github_api, ssl_verify=ssl_verify)

    click.echo("\nCreate new issues at https://github.com/{login}/{name}/issues".format(
        login=entity.login,
        name=name
    ))
    click.echo("Visit your new status page at https://{login}.github.io/{name}/".format(
        login=entity.login,
        name=name
    ))

    click.secho("\nYour status page is now set up and ready!\n", fg="green")
    click.echo("Please note: You need to run the 'statuspage update' command whenever you update or create an issue.\n")

    click.echo("\nIn order to update this status page, run the following command:")
    click.echo("statuspage update --name={name} --token={token} {org}".format(
            name=name, token=token, org="--org=" + entity.login if org else ""))



def iter_systems(labels, system_color):
    for label in labels:
        if label.color == system_color:
            yield label.name


def get_files(repo):
    """
    Get a list of all files.
    """
    return [file.path for file in repo.get_contents("/", ref="gh-pages")]


def get_config(repo, branch_pages):
    """
    Get the config for the repo, merged with the default config. Returns the default config if
    no config file is found.
    """
    files = get_files(repo)
    config = DEFAULT_CONFIG
    if "config.json" in files:
        # get the config file, parse JSON and merge it with the default config
        config_file = repo.get_contents('config.json', ref=branch_pages)
        try:
            repo_config = json.loads(config_file.decoded_content.decode("utf-8"))
            config.update(repo_config)
        except ValueError:
            click.secho("WARNING: Unable to parse config file. Using defaults.", fg="yellow")
    return config


def get_severity(labels, status_labels):
    for label in labels:
        if label.name in status_labels:
            return label.name
    return None


def get_panels(systems):
    # initialize and fill the panels with affected systems
    panels = OrderedDict()
    for system, data in systems.items():
        if data["status"] != "operational":
            if data["status"] in panels:
                panels[data["status"]].append(system)
            else:
                panels[data["status"]] = [system, ]
    return panels


def get_repo(token, name, org, github_api, ssl_verify):
    gh = Github(login_or_token=token, base_url=github_api, verify=ssl_verify)
    if org:
        return gh.get_organization(org).get_repo(name=name)
    return gh.get_user().get_repo(name=name)


def get_collaborators(repo):
    return [col.login for col in repo.get_collaborators()]


def get_systems(repo, issues, system_color, status_labels):
    systems = OrderedDict()
    # get all systems and mark them as operational
    for name in sorted(iter_systems(repo.get_labels(), system_color)):
        systems[name] = {
            "status": "operational",
        }

    for issue in issues:
        if issue.state == "open":
            labels = issue.get_labels()
            severity = get_severity(labels, status_labels)
            affected_systems = list(iter_systems(labels, system_color))
            # shit is hitting the fan RIGHT NOW. Mark all affected systems
            for affected_system in affected_systems:
                systems[affected_system]["status"] = severity
    return systems


def get_incidents(repo, issues, system_color, status_labels):
    # loop over all issues in the past 90 days to get current and past incidents
    incidents = []
    collaborators = get_collaborators(repo=repo)
    for issue in issues:
        labels = issue.get_labels()
        affected_systems = sorted(iter_systems(labels, system_color))
        severity = get_severity(labels, status_labels)

        # make sure that non-labeled issues are not displayed
        if not affected_systems or (severity is None and issue.state != "closed"):
            continue

        # make sure that the user that created the issue is a collaborator
        if issue.user.login not in collaborators:
            continue

        # create an incident
        incident = {
            "created": issue.created_at,
            "title": issue.title,
            "systems": affected_systems,
            "severity": severity,
            "closed": issue.state == "closed",
            "body": markdown2.markdown(issue.body),
            "updates": []
        }

        for comment in issue.get_comments():
            # add comments by collaborators only
            if comment.user.login in collaborators:
                incident["updates"].append({
                    "created": comment.created_at,
                    "body": markdown2.markdown(comment.body)
                })

        incidents.append(incident)

    # sort incidents by date
    return sorted(incidents, key=lambda i: i["created"], reverse=True)


def get_issues(repo):
    return repo.get_issues(state="all", since=datetime.now() - timedelta(days=90))


def is_same_content(c1, c2):
    def sha1(c):
        if PY3:
            if isinstance(c, str):
                c = bytes(c, "utf-8")
        else:
            c = c.encode("utf-8")
        return hashlib.sha1(c)
    return sha1(c1).hexdigest() == sha1(c2).hexdigest()


if __name__ == '__main__':  # pragma: no cover
    cli()
