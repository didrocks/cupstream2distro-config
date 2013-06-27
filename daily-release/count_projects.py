#!/usr/bin/python3

import os, yaml

projects_nb=0
stacks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'stacks')
for release in ('head', 'raring'):
    print("######", release, "######")
    for stack in os.listdir(os.path.join(stacks_path, release)):
        # discare backup stacks
        if not stack.endswith('.cfg'):
            continue
        config = yaml.load(open(os.path.join(stacks_path, release, stack)))
        if not config['stack']['projects']:
            continue
        print("## Stack", stack, '##')
        for project in config['stack']['projects']:
            try:
                if config['stack']['projects'][project] is None or config['stack']['projects'][project]['daily_release'] != False:
                    projects_nb = projects_nb + 1
                    print (project)
            except KeyError:
                projects_nb = projects_nb + 1
                print(project)
print ("projects daily releasing: ", projects_nb)
