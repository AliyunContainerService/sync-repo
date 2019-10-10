#!/usr/bin/python
# -*- coding: utf-8 -*-
import docker
import sys
import os
import getopt
import traceback
import requests
import datetime
import time
import dateutil.parser
import re
import subprocess
import json


tag_filters = ['canary$', 'dev$', '.*-alpha.*']


def match_tag(tag):
    for filter in tag_filters:
        if re.match(filter, tag):
            return True
    return False


def help():
    print('python sync_images -h|--help')
    print('python sync_images [-f|--file <config_file>] [-r|--registry <host:port>] [-n|--namespace] [-i|--insecure_registry] [-d|--days=15]')
    sys.exit(1)


def normalize_repo(repo):
    repo_names = repo.split('/', 2)
    if len(repo_names) == 1:
        repo_names = ['docker.io', 'library', repo_names[0]]
    if len(repo_names) == 2:
        repo_names = ['docker.io', repo_names[0], repo_names[1]]
    return repo_names


def searchTags(url, key):
    r = requests.get(url)
    print('Search repository %s from url %s ...' % (repo, url))
    if r.status_code == 200:
        return r.json().get(key, [])
    else:
        print('Failed to list image tags with error code:%d message:%s' % (r.status_code, r.text))
        return {}

def run(cmd):
    return subprocess.check_output(cmd, shell=True)

def searchTagsWith(cmd, key):
    output = run(cmd)
    print('Search repository %s with cmd %s ...' % (repo, cmd))
    return json.loads(output).get("data").get(key, [])

def list_repo_tags(client, repo):
    result = []
    repo_names = normalize_repo(repo)
    timestamp = time.mktime((datetime.date.today() - datetime.timedelta(days=days)).timetuple()) * 1000
    if repo_names[0] == 'docker.io':
        url = "https://registry.hub.docker.com/v2/repositories/%s/%s/tags/?page_size=1024" % (repo_names[1], repo_names[2])
        tags = searchTags(url, 'results')
        for image in tags:
            timeUpload = time.mktime(dateutil.parser.parse(image['last_updated']).timetuple())*1000
            tag = image['name']
            if len(tags) > 0 and timeUpload > timestamp:
                result.append(tag)
    elif repo_names[0] == 'quay.io':
        url = 'https://quay.io/api/v1/repository/%s/%s/tag/' % (repo_names[1], repo_names[2])
        tags = searchTags(url, 'tags')
        for image in tags:
            timeUpload = float(image['start_ts']) * 1000
            tag = image['name']
            if len(tags) > 0 and timeUpload > timestamp:
                result.append(tag)
    elif repo_names[0].endswith("aliyuncs.com"):
        # url = 'https://quay.io/api/v1/repository/%s/%s/tag/' % (repo_names[1], repo_names[2])
        # | jq '.data'
        endpoint = repo_names[0].split(".")[1]
        cmd = "aliyun cr GET  /repos/%s/%s/tags --endpoint cr.%s.aliyuncs.com"  % (repo_names[1], repo_names[2], endpoint)
        tags = searchTagsWith(cmd, 'tags')
        if len(tags) > 0:
            print("Sync repo %s/%s: " % (repo_names[1], repo_names[2]))
        for image in tags:
            timeUpload = float(image['imageUpdate']) #* 1000
            tag = image['tag']
            # print("image tags: %s, timeUpload: %s, start_time %s" % (tag, timeUpload, timestamp))
            # Only list the layer with tag and later than timestamp
            if len(tags) > 0 and timeUpload > timestamp:
                print("image tags: %s, timeUpload: %s, start_time %s" % (tag, timeUpload, timestamp))
                result.append(tag)
    else:
        url = 'https://%s/v2/%s/%s/tags/list' % (repo_names[0], repo_names[1], repo_names[2])
        manifest = searchTags(url, u'manifest')
        for key in manifest:
            image = manifest[key]
            timeUpload = float(image[u'timeUploadedMs'])
            tags = image[u'tag']

            # Only list the layer with tag and later than timestamp
            if len(tags) > 0 and timeUpload > timestamp:
                for tag in tags:
                    # Ignore the canary and alpha images
                    if not match_tag(tag):
                        print('Tags %s uploaded %s' % (tag, image[u'timeUploadedMs']))
                        result.append(tag)

    result = list(set(result))
    return result


def sync_repo(client, registry, namespace, insecure_registry, repo, newName):
    print('Syncing repository %s ...' % repo)
    tags = list_repo_tags(client, repo)

    new_repo_name = registry + '/' + namespace + '/' + newName

    print('Original repository is %s' % repo)
    print('New repository is %s' % new_repo_name)

    for tag in tags:
        try:
            print('Pulling %s:%s' % (repo, tag))
            image = client.images.pull(repo, tag=tag)
            print('Tagging %s:%s %s:%s' % (repo, tag, new_repo_name, tag))
            image.tag(new_repo_name, tag)
            print('Pushing repository %s:%s ...' % (new_repo_name, tag))
            client.images.push(new_repo_name, tag=tag)
        except Exception:
            traceback.print_exc()
    print('Complete the sync of repository %s' % repo)


options = []
DEFAULT_CONFIG_FILE = './images.txt'
DEFAULT_REGISTRY = 'registry.cn-hangzhou.aliyuncs.com'
DEFAULT_NAMESPACE = 'google_containers'
INSECURE_REGISTRY = False
DEFAULT_DAYS = 15

docker_host = None
insecure_registry = INSECURE_REGISTRY
filename = DEFAULT_CONFIG_FILE
days = DEFAULT_DAYS
# parse command line arguments

try:
    (options, args) = getopt.getopt(sys.argv[1:], 'f:d:r:n:ih', ['file=', 'days=', 'registry=', 'namespace=', 'insecure_registry', 'help'])
except getopt.GetoptError:
    help()
namespace = DEFAULT_NAMESPACE
registry = DEFAULT_REGISTRY
for option in options:
    if option[0] == '-f' or option[0] == '--file':
        filename = option[1]
    elif option[0] == '-r' or option[0] == '--registry':
        registry = option[1]
    elif option[0] == '-n' or option[0] == '--namespace':
        namespace = option[1]
    elif option[0] == '-i' or option[0] == '--insecure_registry':
        insecure_registry = True
    elif option[0] == '-d' or option[0] == '--days':
        days = int(option[1])
    elif option[0] == '-h' or option[0] == '--help':
        help()

if not os.path.exists(filename):
    print >> sys.stderr, 'Cannot file configuration for image sync: %s' \
        % filename
    sys.exit(1)
lines = [line.strip() for line in open(filename)]

print('Syncing images within %d days ...' % days)
# client = docker.Client(docker_host)

client = docker.from_env()

for line in lines:

    # Ignore comment

    if line.startswith('#'):
        continue
    if line == '':
        continue
    try:
        repos = line.split("=")
        if len(repos) == 1:
            # Get the repo name
            repo=line
            repo_names = normalize_repo(repo)
            new_repo = repo_names[2]
        else:
            repo = repos[0]
            repo_names = normalize_repo(repos[1])
            registry = repo_names[0]
            namespace = repo_names[1]
            new_repo = repo_names[2]
        sync_repo(client, registry, namespace, insecure_registry, repo, new_repo)
    except Exception:
        traceback.print_exc()
