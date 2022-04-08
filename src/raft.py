#!/usr/bin/env python3

# Run this *in* the RAFT directory, or bad things will happen (or nothing at all).

import argparse
from glob import glob
import hashlib
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tarfile
import time

from git import Repo

# These are repeatedly called, so trying to make life easier.
from os.path import join as pjoin
from os import getcwd


def get_args():
    """
    Collecting user-defined arguments.
    """
    parser = argparse.ArgumentParser(prog="RAFT",
                                     description="""Reproducible
                                                    Analyses
                                                    Framework
                                                     and
                                                    Tools""")

    subparsers = parser.add_subparsers(dest='command')

    # Subparser for initial RAFT setup.
    parser_setup = subparsers.add_parser('setup',
                                         help="""RAFT setup and configuration.""")
    parser_setup.add_argument('-d', '--default',
                              help="Use default paths for setup.",
                              action='store_true',
                              default=False)

    # Subparser for initializing a project.
    parser_init_project = subparsers.add_parser('init-project',
                                                help="Initialize a RAFT project.")
    parser_init_project.add_argument('-c', '--init-config',
                                     help="Project config file (see documentation).",
                                     default=pjoin(getcwd(), '.init.cfg'))
    parser_init_project.add_argument('-p', '--project-id',
                                     help="Project identifier",
                                     required=True)
    parser_init_project.add_argument('-r', '--repo-url',
                                     help="Git repo url for remote pushing/pulling.",
                                     default='')

    # Subparser for loading a manifest into a project.
    parser_load_manifest = subparsers.add_parser('load-manifest',
                                                 help="Load manifest into a project.")
    parser_load_manifest.add_argument('-c', '--manifest-csv',
                                      help="Manifest CSV (see documentation)",
                                      required=True)
    parser_load_manifest.add_argument('-p', '--project-id',
                                      help="Project identifier",
                                      required=True)

    # Subparser for loading reference files/dirs into a project.
    parser_load_reference = subparsers.add_parser('load-reference',
                                                  help="Loads ref files/dirs into a project.")
    parser_load_reference.add_argument('-f', '--file',
                                       help="Reference file or directory (see documentation).",
                                       required=True)
    parser_load_reference.add_argument('-s', '--sub-dir',
                                       help="Subdirectory for reference file or directory.",
                                       default='')
    parser_load_reference.add_argument('-p', '--project-id',
                                       help="Project identifier",
                                       required=True)
    parser_load_reference.add_argument('-m', '--mode',
                                       help="Mode (copy or symlink). Default: symlink",
                                       default='symlink')

    # Subparser for loading metadata into a project.
    parser_load_metadata = subparsers.add_parser('load-metadata',
                                                 help="Loads metadata into a project.")
    parser_load_metadata.add_argument('-f', '--file',
                                      help="Metadata file. Check docs for more info.",
                                      required=True)
    parser_load_metadata.add_argument('-s', '--sub-dir',
                                      help="Subdirectory for metadata file.", default='')
    parser_load_metadata.add_argument('-p', '--project-id',
                                      help="Project identifier.",
                                      required=True)
    parser_load_metadata.add_argument('-m', '--mode',
                                      help="Mode (copy or symlink). Default: copy",
                                      default='symlink')

    # Subparser for loading a complete dataset into a project.
    parser_load_dataset = subparsers.add_parser('load-dataset',
                                                help="Loads dataset into aa project.")
    parser_load_dataset.add_argument('-d', '--dataset-id',
                                     help="Dataset identifier. Check docs for more info.",
                                     required=True)
    parser_load_dataset.add_argument('-p', '--project-id',
                                     help="Project identifier",
                                     required=True)
    parser_load_dataset.add_argument('-r', '--repo',
                                     help="Repo to load module from",
                                     default='')
    parser_load_dataset.add_argument('-b', '--branch',
                                     help="Branch to load for module",
                                     default='master')
    parser_load_dataset.add_argument('-m', '--mode',
                                     help="Mode (copy or symlink). Default: copy",
                                     default='symlink')

    # Subparser for loading component into a project.
    parser_load_module = subparsers.add_parser('load-module',
                                               help="Clones Nextflow module into project.")
    parser_load_module.add_argument('-p', '--project-id',
                                    help="Project identifier",
                                    required=True)
    parser_load_module.add_argument('-r', '--repo',
                                    help="Module repository.",
                                    default='')
    parser_load_module.add_argument('-m', '--module',
                                    help="Module to add to project.",
                                    required=True)
    # Need support for commits and tags here as well.
    parser_load_module.add_argument('-b', '--branches',
                                    help="Branches to checkout per module (see documentat). Default='main'.",
                                    default='main')
    parser_load_module.add_argument('-n', '--no-deps',
                                    help="Do not automatically load dependencies.",
                                    default=False)
    parser_load_module.add_argument('-d', '--delay',
                                    help="Delay (in seconds) before git pulls. (Default = 15s).",
                                    default=15)

    # Subparser for listing module steps.
    parser_list_steps = subparsers.add_parser('list-steps',
                                              help="List module's processes and workflows.")
    parser_list_steps.add_argument('-p', '--project-id',
                                   help="Project identifier",
                                   required=True)
    parser_list_steps.add_argument('-m', '--module',
                                   help="Module")
    parser_list_steps.add_argument('-s', '--step',
                                   help="Step")

    # Subparser for updating project-specific mounts.config file.
    parser_update_mounts = subparsers.add_parser('update-mounts',
                                                 help="""Updates project-specific mounts.config
                                                         file with symlinks found in a directory.""")
    parser_update_mounts.add_argument('-p', '--project-id',
                                      help="Project identifier",
                                      required=True)
    parser_update_mounts.add_argument('-d', '--dir',
                                      help="Directory containing symlinks for mounts.config.",
                                      required=True)

    # Subparser for adding a step into workflow step of a project.
    parser_add_step = subparsers.add_parser('add-step',
                                            help="""Add step (process/workflow) to project
                                                    (see documentation).""")
    parser_add_step.add_argument('-p', '--project-id',
                                 help="Project identifier",
                                 required=True)
    parser_add_step.add_argument('-m', '--module',
                                 help="Module containing step (process/workflow).",
                                 required=True)
    parser_add_step.add_argument('-s', '--step',
                                 help="Process/workflow to add.",
                                 required=True)
    parser_add_step.add_argument('-S', '--subworkflow',
                                 help="Subworkflow to add step to (default: main)",
                                 default='main')
    parser_add_step.add_argument('-a', '--alias',
                                 help="Assign an alias to step.",
                                 default='')

    # Subparser for running workflow.
    parser_run_workflow = subparsers.add_parser('run-workflow',
                                                help="Run workflow")
    parser_run_workflow.add_argument('--no-resume',
                                     help="Do not use Nextflow's -resume.",
                                     default=False,
                                     action='store_true')
    parser_run_workflow.add_argument('-w', '--workflow',
                                     help="Workflow to run (default: main).",
                                     default='main')
    parser_run_workflow.add_argument('-n', '--nf-params',
                                     help="Parameter string passed to Nextflow (see documentation).")
    parser_run_workflow.add_argument('-p', '--project-id',
                                     help="Project identifier",
                                     required=True)
    parser_run_workflow.add_argument('-k', '--keep-previous-outputs',
                                     help="Do not remove previous outputs before running.",
                                     action='store_true')
    parser_run_workflow.add_argument('-r', '--no-reports',
                                     help="Do not create report files.",
                                     action='store_true')

    # Subparser for packaging project (to generate sharable rftpkg tar file)
    parser_package_project = subparsers.add_parser('package-project',
                                                   help="Package project (see documentation).")
    parser_package_project.add_argument('-p', '--project-id',
                                        help="Project identifier")
    parser_package_project.add_argument('-o', '--output',
                                        help="Output file.",
                                        default='')
    parser_package_project.add_argument('-n', '--no-git',
                                        help="Do not include Git files.",
                                        default=False,
                                        action='store_true')
    parser_package_project.add_argument('-c', '--no-checksums',
                                        help="Do not include checksums.",
                                        default=False,
                                        action='store_true')

    # Subparser for loading package (after receiving rftpkg tar file)
    parser_load_project = subparsers.add_parser('load-project',
                                                help="Load project (see documentation).")
    parser_load_project.add_argument('-p', '--project-id', help="Project identifier")
    parser_load_project.add_argument('-r', '--rftpkg', help="rftpkg file")
    parser_load_project.add_argument('--repo-url', help="Git repo url.")
    parser_load_project.add_argument('--branch', help="Git repo branch.", default='master')

    # Subparser for pushing package
    parser_push_project = subparsers.add_parser('push-project',
                                                help="Push project to repo(see documentation).")
    parser_push_project.add_argument('-p', '--project-id', help="Project identifier")
    parser_push_project.add_argument('-r', '--rftpkg', help="rftpkg file.")
    parser_push_project.add_argument('--repo', help="Repo push to.")
    parser_push_project.add_argument('-c', '--comment', help="Commit comment.")
    parser_push_project.add_argument('-b', '--branch', help="Git branch.")

    # Subparser for pulling package from repo
    parser_pull_project = subparsers.add_parser('pull-project',
                                                help="Pull project from repo (see documentation).")
    parser_pull_project.add_argument('-p', '--project-id', help="Project identifier")
    parser_pull_project.add_argument('-r', '--rftpkg', help="rftpkg file")

    parser_update_modules = subparsers.add_parser('update-modules',
                                                  help="Pull the latest commits for each module.")
    parser_update_modules.add_argument('-p', '--project-id', help="Project identifier")
    parser_update_modules.add_argument('-m', '--modules',
                                       help="List of modules to update (Default = all)",
                                       default='')

    parser_rename_project = subparsers.add_parser('rename-project',
                                                  help="Rename a project exhaustively.")
    parser_rename_project.add_argument('-p', '--project-id', help="Project identifier")
    parser_rename_project.add_argument('-n', '--new-id', help="New project identifier")

    # Subparser for cleaning work directories associated with a project.
    parser_clean_project = subparsers.add_parser('clean-project',
                                                 help="Remove unneeded (failed/aborted) work directories for a project.")
    parser_clean_project.add_argument('-p', '--project-id', help="Project.")
    parser_clean_project.add_argument('-k', '--keep-latest',
                                      help="Keep only directories from latest successful run.",
                                      action='store_true', default=False)
    parser_clean_project.add_argument('-n', '--no-exec',
                                      help="Provide latest/completed/cleanable work directory counts but do NOT delete.",
                                      action='store_true', default=False)

    # Subparser for copying parameters between projects or from a config file.
    parser_copy_params = subparsers.add_parser('copy-parameters',
                                               help="copy parameters between projects.")
    parser_copy_params.add_argument('-s', '--source-project',
                                      help="Source project identifier")
    parser_copy_params.add_argument('-d', '--destination-project',
                                      help="Destination project identifier")
    parser_copy_params.add_argument('-c', '--source-config',
                                      help="Source configuration file (to copy parameters from)")

    return parser.parse_args()

def setup(args):
    """
    Part of the setup mode.

    Installs RAFT into current working directory.
    Installation consists of:

        - Moving any previously generated RAFT configuration files.

        #Paths
        - Prompting user for paths for paths shared amongst analyses (if not using -d/--default).

        #NF Repos
        - Prompting user for git urls for module-level repositories.

        #RAFT Repos
        - Prompting user for git urls for RAFT-specific repositories (storing rftpkgs).

        #Saving
        - Saving these urls in a JSON format in ${PWD}/.raft.cfg

        #Executing
        - Making the required shared paths.
        - Checking out RAFT-specific repositories to repos directory specific in cfg.

    Args:
        # This requires more information. What are the keys of this object?
        args (Namespace object): User-provided arguments.
    """
    print("Setting up RAFT...\n")
    if args.default:
        print("Using defaults due to -d/--default flag...")

    # DEFAULTS
    raft_paths = {'projects': pjoin(getcwd(), 'projects'),
                  'references': pjoin(getcwd(), 'references'),
                  'fastqs': pjoin(getcwd(), 'fastqs'),
                  'imgs': pjoin(getcwd(), 'imgs'),
                  'metadata': pjoin(getcwd(), 'metadata'),
                  'shared': pjoin(getcwd(), 'shared')}

    init_cfg = {"indicies": "",
                "references": "",
                "fastqs": "",
                "tmp": "",
                "outputs": "",
                "workflow": "",
                "work": "",
                "metadata": "",
                "logs": "",
                "rftpkgs": "",
                "raft": ""}

    with open(pjoin(getcwd(), '.init.cfg'), 'w') as fo:
        json.dump(init_cfg, fo)

    with open(pjoin(getcwd(), '.init.wf'), 'w') as fo:
        fo.write('#!/usr/bin/env nextflow\n')
        fo.write('nextflow.enable.dsl=2\n')
        fo.write('\n')
        fo.write('/*General Parameters*/\n')
        fo.write("params.project_dir = ''\n")
        fo.write('params.fq_dir = "${params.project_dir}/fastqs"\n')
        fo.write("params.global_fq_dir = ''\n")
        fo.write("params.shared_dir = ''\n")
        fo.write('params.metadata_dir = "${params.project_dir}/metadata"\n')
        fo.write('params.indices_out_dir = "${params.project_dir}/indices"\n')
        fo.write('params.ref_dir = "${params.project_dir}/references"\n')
        fo.write('params.output_dir = "${params.project_dir}/outputs"\n')
        fo.write('params.dsp_output_dir = "${params.output_dir}/dataset_prep"\n')
        fo.write('params.analyses_dir = "${params.output_dir}/analyses"\n')
        fo.write('params.batch_dir = "${params.output_dir}/batch"\n')
        fo.write('params.gene_sigs_dir = "${params.batch_dir}/gene_signatures"\n')
        fo.write('params.samps_out_dir = "${params.output_dir}/samples"\n')
        fo.write('params.qc_out_dir = "${params.output_dir}/qc"\n')
        fo.write('\n')
        fo.write('/*Fine-tuned Parameters*/\n')
        fo.write('\n')
        fo.write('/*Inclusions*/\n')
        fo.write('\n')
        fo.write('/*Workflows*/\n')
        fo.write('\n')
        fo.write('workflow {\n')
        fo.write('}\n')

    with open(pjoin(getcwd(), '.nextflow.config'), 'w') as fo:
        fo.write("manifest.mainScript = 'main.nf'\n")
        fo.write("\n")
        fo.write("process {\n")
        fo.write("}\n")


    git_prefix = 'https://gitlab.com/bgv-lens/nextflow'
    #nextflow-components is a subgroup, not a repo.
    nf_repos = {'nextflow_modules': pjoin(git_prefix, 'Modules')}
    nf_subs = {'nextflow_module_subgroups': ['Tools', 'Projects', 'Datasets']}

    raft_repos = {}

    # Ideally, users should be able to specify where .raft.cfg lives but RAFT
    # needs an "anchor" for defining other directories.
    cfg_path = pjoin(getcwd(), '.raft.cfg')

    # Make backup of previous configuration file.
    if os.path.isfile(cfg_path):
        bkup_cfg_path = cfg_path + '.orig'
        print("A configuration file already exists.")
        print("Copying original to {bkup_cfg_path}.")
        os.rename(cfg_path, bkup_cfg_path)

    if not args.default:
        # Setting up filesystem paths.
        raft_paths = get_user_raft_paths(raft_paths)

        # Setting up Nextflow module repositories.
        nf_repos, nf_subs = get_user_nf_repos(nf_repos, nf_subs)

    master_cfg = {'filesystem': raft_paths,
                  'nextflow_repos': nf_repos,
                  'nextflow_subgroups': nf_subs,
                  'analysis_repos': raft_repos}

    print("Saving configuration file to {cfg_path}...")
    dump_cfg(cfg_path, master_cfg)

    print("Executing configuration file...")
    setup_run_once(master_cfg)

    print("Setup complete.")


def get_user_raft_paths(raft_paths):
    """
    Part of setup mode.

    NOTE: The language should really be cleared up here. Users should
    understand that the keys are simply names while the values are actual
    filesystem paths.

    Prompts user for desired path for directories to be shared among analyses
    (e.g. indexes, fastqs, etc.)

    Args:
        raft_paths (dict): Dictionary containing RAFT paths (e.g. indexes,
                           fastqs, etc.) as keys and the default path as
                           values.

    Returns:
        Dictionary containing RAFT paths as keys and user-specified directories as values.
    """
    print("WARNING: The work directory will be large. Choose accordingly.")
    for raft_path, default in raft_paths.items():
        user_spec_path = input("Provide a global (among projects) directory for {raft_path} (Default: {default}): ")
        # Should be doing some sanity checking here to ensure the path can exist.
        if user_spec_path:
            if re.search('~', user_spec_path):
                user_spec_path = os.path.realpath(os.path.expanduser(user_spec_path))
            raft_paths[raft_path] = user_spec_path
    return raft_paths


def get_user_nf_repos(nf_repos, nf_subs):
    """
    Part of setup mode.

    Prompts user for desired Nextflow reposities.
    Examples include:
        nextflow-components

    Args:
        nf_repos (dict): Dictionary containing repo names as keys and git url as values.

    Returns:
        Dictionary containing repo names as keys and user-specific git urls as values.
    """
    # Allow users to specify their own Nextflow workflows and modules repos.
    for nf_repo, default in nf_repos.items():
        user_spec_repo = input("\nProvide a repository for Nextflow {nf_repo}\n(Default: {default}):")
        if user_spec_repo:
            nf_repos[nf_repo] = user_spec_repo

    # This should be in its own function.
    for nf_sub, default in nf_subs.items():
        user_spec_subs = input("\nProvide a comma separated list for Nextflow Module subgroups \n(Default: {}):"
                               .format(default))
        if user_spec_subs:
            nf_subs[nf_sub] = user_spec_subs

    return nf_repos, nf_subs


def dump_cfg(cfg_path, master_cfg):
    """
    Part of setup mode.

    TODO: Add exception handling.

    Writes configuration file to cfg_path.

    Args:
        cfg_path (str): Path for writing output file.
        master_cfg (dict): Dictionary containing configuration information.
    """
    with open(cfg_path, 'w') as fo:
        json.dump(master_cfg, fo, indent=4)


def setup_run_once(master_cfg):
    """
    Part of setup mode.

    Makes/symlinks directories in the 'filesystem' portion of configuration
    file. Clones/initializes any RAFT repositories.

    Args:
        master_cfg (dict): Dictionary with configuration information.
    """
    for dir in master_cfg['filesystem'].values():
        if os.path.isdir(dir): # Need to ensure dir isn't already in RAFT dir.
            print("Symlinking {} to {}...".format(dir, getcwd()))
            try:
                os.symlink(dir, pjoin(getcwd(), os.path.basename(dir)))
            except:
                print("{} already exists.".format(dir))
        else:
            print("Making {}...".format(dir))
            os.mkdir(dir)


def init_project(args):
    """
    Part of init-project mode.

    Initializes project.

    Initializing a project includes:
      - Make a project directory within RAFT /projects directory.
      - Populate project directory using information within specificed
        init_config file.
      - Make a mounts.config file to allow Singularity to access RAFT directories.
      - Make auto.raft file (which records steps taken within RAFT).
      - Create workflow/modules/ directory and project.nf overall workflow.

    Args:
        args (Namespace object): User-provided arguments
    """
    proj_dir = mk_proj_dir(args.project_id)
    bound_dirs = fill_dir(args, proj_dir, args.init_config,)
    mk_mounts_cfg(proj_dir, bound_dirs)
    mk_auto_raft(args)
    mk_main_wf_and_cfg(args)
    mk_repo(args)


def mk_repo(args):
    """
    """
    raft_cfg = load_raft_cfg()
    local_repo = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'rftpkgs')
    repo = Repo.init(local_repo)
    if args.repo_url:
        repo.create_remote('origin', args.repo_url)


def mk_main_wf_and_cfg(args):
    """
    Part of the init-project mode.

    Copies default main.nf template and creates sparse nextflow.config.

    Args:
        args (Namespace object): User-provided arguments
    """
    raft_cfg = load_raft_cfg()
    tmplt_wf_file = os.path.join(os.getcwd(), '.init.wf')
    tmplt_cfg_file = os.path.join(os.getcwd(), '.nextflow.config')
    proj_wf_path = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow')
    with open(tmplt_wf_file) as origfo:
        with open(pjoin(proj_wf_path, 'main.nf'), 'w') as outfo:
            for line in origfo.readlines():
                if line == "params.project_dir = ''\n":
                    line = "params.project_identifier = '{}'\nparams.project_dir = ''\n".format(args.project_id)
                outfo.write(line)

    shutil.copyfile(tmplt_cfg_file, pjoin(proj_wf_path, 'nextflow.config'))

    # Adding Singularity info and making nextflow.config.
    imgs_dir = raft_cfg['filesystem']['imgs']
    cfg_out = ["manifest.mainScript = 'main.nf'\n\n"]
    cfg_out.append('singularity {\n')
    cfg_out.append('  cacheDir = "{}"\n'.format(imgs_dir))
    cfg_out.append("  autoMount = 'true'\n")
    cfg_out.append('}\n')

    with open(pjoin(proj_wf_path, 'nextflow.config')) as fo:
        cfg_out.extend(fo.readlines()[1:])
    proc_idx = cfg_out.index("process {\n")
    mounts_cfg_path = pjoin(proj_wf_path, 'mounts.config')
    cfg_out.insert(proc_idx + 1, "containerOptions = '-B `cat {}`'\n".format(mounts_cfg_path))

    with open(pjoin(proj_wf_path, 'nextflow.config'), 'w') as fo:
        for row in cfg_out:
            fo.write(row)


def mk_auto_raft(args):
    """
    Part of the init-project mode.

    Makes auto.raft file (within Analysis /.raft directory). auto.raft keeps
    track of RAFT commands executed within a project.

    Args:
        args (Namespace object): User-provided arguments
    """
    raft_cfg = load_raft_cfg()
    auto_raft_file = pjoin(raft_cfg['filesystem']['projects'],
                           args.project_id,
                           '.raft',
                           'auto.raft')

    with open(auto_raft_file, 'w') as fo:
        fo.write("{}\n".format(' '.join(sys.argv)))


def mk_proj_dir(proj_id):
    """
    Part of the init-project mode.

    Makes the project directory within the RAFT /projects directory.

    Args:
        name (str): Project identifier.

    Returns:
        str containing the generated project path.
    """
    proj_dir = ''
    raft_cfg = load_raft_cfg()
    global_dir = raft_cfg['filesystem']['projects']
    proj_dir = pjoin(global_dir,proj_id)

    try:
        os.mkdir(proj_dir)
    except FileExistsError:
        sys.exit("Project directory already exists. Please try another.")

    return proj_dir


def fill_dir(args, dir, init_cfg):
    """
    Part of the init-project mode.

    Populates a project directory with template defined in init_cfg. Returns
    a list of directories to be included in the mounts.config file for the
    project.

    Args:
        args (Namespace object):
        dir (str): Project path.
        init_cfg (str): Initialization configuration path. File should be in
                        JSON format.

    Returns:
        bind_dirs (list): List of directories to be included in mounts.config
                           file.
    """
    # Getting the directories to be bound by this function as well. This should
    # probably be done a different way.
    bind_dirs = []
    raft_cfg = load_raft_cfg()
    req_sub_dirs = {}
    with open(init_cfg) as fo:
        req_sub_dirs = json.load(fo)
    for name, sdir in req_sub_dirs.items():
        # If the desired directory has an included path, link that path to
        # within the project directory. This should include some sanity
        # checking to ensure the sub_dir directory even exists.
        if sdir:
            os.symlink(sdir, pjoin(dir, name))
        # Else if the desired directory doesn't have an included path, simply
        # make a directory by that name within the project directory.
        elif not sdir:
            os.mkdir(pjoin(dir, name))
    bind_dirs.append(pjoin(raft_cfg['filesystem']['projects'], args.project_id))
    bind_dirs.append(raft_cfg['filesystem']['work'])
    bind_dirs.append(getcwd())

    # Bindable directories are returned so they can be used to generate
    # mounts.config which allows Singularity (and presumably Docker) to bind
    # (and access) these directories.
    return bind_dirs


def mk_mounts_cfg(dir, bind_dirs):
    """
    Part of the init-project mode.

    Creates a mounts.config file for a project. This file is provided to
    Nextflow and used to bind directories during Singularity execution. This
    will have to be modified to use Docker, but works sufficiently for
    Singularity now.

    Args:
        dir (str): Analysis path.
        bind_dirs (list): Directories to be included in mounts.config file.
    """
    raft_cfg = load_raft_cfg()
    out = []
    out.append('{}\n'.format(','.join(bind_dirs)))

    with open(pjoin(dir, 'workflow', 'mounts.config'), 'w') as fo:
        for row in out:
            fo.write(row)


def update_mounts_cfg(mounts_cfg, bind_dirs):
    """
    Part of update-mounts mode.

    Updates a mount.config file for a project.

    This is primarily intended to update the mount.config file with absolute
    paths for symlinked FASTQs, but can also be used generally.

    Args:
        mount_cfg (str): Path to mounts.config file to update.
        bind_dirs (list): Directories to be included in mounts.config file.
    """
    out = []
    with open(mounts_cfg, 'r') as ifo:
        line = ifo.readline()
        line = line.strip('\n')
        paths = line.split(',')
        bind_dirs_to_add = []
        for bind_dir in bind_dirs:
            if not any([bind_dir.startswith(path) for path in paths]):
                bind_dirs_to_add.append(bind_dir)
            for path in paths:
                if path.startswith(bind_dir):
                    paths.remove(path)
        paths.extend(bind_dirs_to_add)
        paths = ','.join(paths) + '\n'
        out.append(paths)

    with open(mounts_cfg, 'w') as fo:
        for row in out:
            fo.write(row)


def update_mounts(args):
    """
    Part of the update-mounts mode.

    This functions finds the real paths of all symlinks within the specified
    directory and adds them the the project-specific mounts.config file.

    Args:
        args (Namespace object)
    """
    raft_cfg = load_raft_cfg()
    bind_dirs = []
    to_check = glob(pjoin(os.path.abspath(args.dir), "**", "*"), recursive=True)
    for fle in to_check:
        bind_dirs.append(os.path.dirname(os.path.realpath(fle)))

    bind_dirs = list(set(bind_dirs))

    if bind_dirs:
        update_mounts_cfg(pjoin(raft_cfg['filesystem']['projects'],
                                args.project_id,
                                'workflow',
                                'mounts.config'),
                          bind_dirs)


def load_manifest(args):
    """
    Part of the load-manifest mode.

    Given a user-provided manifest CSV file:
        - Copy file to project's /metadata directory.
        - Checks to see if any prefixes in any column labeled "File_Prefix" are
          present in the global RAFT /fastqs directory.
        - Symlink FASTQs to from global RAFT /fastqs directory project-specific
          /fastqs directory.

    NOTE: This function will eventually handle more than FASTQs prefixes.

    Args:
        args (Namespace object): User-provided arguments.
    """
    raft_cfg = load_raft_cfg()
    print("Loading manifest into project {}...".format(args.project_id))
    overall_mani = pjoin(raft_cfg['filesystem']['projects'],
                         args.project_id,
                         'metadata',
                         args.project_id + '_manifest.csv')

    # Check the global RAFT FASTQ directory for FASTQs.
    global_fastqs_dir = pjoin(raft_cfg['filesystem']['fastqs'])
    local_fastqs_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'fastqs')

    # Glob the manifest from the global metadata directory.
    global_csv = glob(pjoin(raft_cfg['filesystem']['metadata'], '**', args.manifest_csv), recursive=True)[0]
    print("Copying metadata file into project metadata directory...")
    if os.path.isdir(pjoin(raft_cfg['filesystem']['projects'], args.project_id)):
        # If the specified project doesn't exist, then should it be created automatically?
        metadata_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'metadata')
        shutil.copyfile(global_csv,
                        pjoin(metadata_dir, os.path.basename(args.manifest_csv)))

    hdrl = ['Sample_ID', 'Patient_ID', 'File_Prefix', 'Dataset', 'Treatment', 'Sample_Type', 'Sequencing_Method', 'Tissue']
    proj_hdr = ','.join(hdrl) + '\n'
    reconfiged_mani = []

    bind_dirs = [] #Stores directories containing absolute path to FASTQs.

    print("Checking contents of manifest csv...")
    with open(global_csv) as fo:
        hdr = fo.readline()
        hdr = hdr.strip('\n').split(',')
        # Will certainly need a better way to do this, but this will work for now.
        cols_to_check = [i for i in range(len(hdr)) if hdr[i] in ['File_Prefix']]
        col_idx_map = {i: j for j, i in enumerate(hdr)}

        for row in fo:
            row = row.strip('\n').split(',')

            #Mention adding manifest to project-level manifest.
            for col in cols_to_check: # Is this needed? Seems like only one column should be used.
                prefix = row[col]
                if prefix == 'NA':
                    continue
                reconfiged_row = []
                for col in hdrl:
                    if col in col_idx_map.keys():
                        reconfiged_row.append(row[col_idx_map[col]])
                    else:
                        reconfiged_row.append('NA')
                reconfiged_mani.append(','.join(reconfiged_row))

                print("Checking for FASTQ prefix {} in global /fastqs...".format(prefix))
                hits = glob(pjoin(global_fastqs_dir, prefix + '*'), recursive=True)
                #Check here to ensure that these FASTQs actually belong to the same sample.
                if hits:
                    print("Found FASTQs for prefix {} in /fastqs!\n".format(prefix))
                    for hit in hits:
                        os.symlink(os.path.realpath(hit), pjoin(local_fastqs_dir, os.path.basename(hit)))
                        #Just adding each file individually for now...
                        bind_dirs.append(os.path.dirname(os.path.realpath(hit)))
                else:
                    print("Unable to find FASTQs for prefix {} in /fastqs. Check your metadata!\n".format(prefix))

    bind_dirs = list(set(bind_dirs))

    update_mounts_cfg(pjoin(raft_cfg['filesystem']['projects'],
                            args.project_id,
                            'workflow',
                            'mounts.config'),
                      bind_dirs)

    with open(overall_mani, 'w') as mfo:
        contents = ''
        try:
            contents = mfo.readlines()
        except:
            pass
        if proj_hdr not in contents:
            mfo.write(proj_hdr)
        mfo.write('\n'.join([row for row in reconfiged_mani if row not in contents]))


def load_metadata(args):
    """
    Part of the load-metadata mode.

    NOTE: This is effectively load_samples without the sample-level checks.
          These can probably be easily consolidated.

    Given a user-provided metadata CSV file:
        - Copy/symlink file to project's /metadata directory.
        - Update project's mounts.config file if metadata file is symlinked.

    Args:
        args (Namespace object): User-provided arguments.
    """
    load_files(args, 'metadata')


def load_reference(args):
    """
    Part of load-reference mode.

    Given a user-provided reference file:
        - Copy/symlink reference file to project's /reference directory.
        - Update project's mounts.config file if reference file is symlinked.

    Args:
        args (Namespace object): User-provided arguments.
    """
    load_files(args, 'references')


def load_files(args, out_dir):
    """
    Generic loading/symlinking function for functions like load_metadata(), load_reference(), etc.

    Args:
        args (Namespace object): User-provided arguments.
        out_dir (str): Output directory for copied/symlinked file.

    """
    raft_cfg = load_raft_cfg()

    base = out_dir # output dir is input dir

    full_base = raft_cfg['filesystem'][base]

    globbed_files =  glob(pjoin(full_base, '**', args.file), recursive=True)
    if len(globbed_files) == 0:
        sys.exit("Cannot find {} in {}/**".format(args.file, full_base))
        # Put list of available references here.
    if len(globbed_files) > 1:
        sys.exit("File name {} is not specific enough. Please provide a directory prefix.".format(args.file))
        # Put list of conflicting files here.
    globbed_file = globbed_files[0]

    abs_out_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id, out_dir)
    if args.sub_dir and not os.path.exists(pjoin(abs_out_dir, args.sub_dir)):
        os.makedirs(pjoin(abs_out_dir, args.sub_dir))

    result_file = pjoin(abs_out_dir, args.sub_dir, os.path.basename(globbed_file))

    if os.path.exists(result_file):
        print("{} already exists within the project. Ignoring load request.".format(result_file))
    elif args.mode == 'symlink':
        os.symlink(os.path.realpath(globbed_file),
                   result_file)

        update_mounts_cfg(pjoin(raft_cfg['filesystem']['projects'],
                                args.project_id,
                                'workflow',
                                'mounts.config'),
                          [os.path.realpath(globbed_file)])

    elif args.mode == 'copy':
        shutil.copyfile(os.path.realpath(globbed_file),
                        result_file)


def recurs_load_modules(args):
    """
    Recurively loads Nextflow modules. This occurs in multiple iterations such
    that each time a dependencies is loaded/cloned, another iteration is initated. This
    continues until an instance in which no new dependencies are loaded/cloned. There's
    probably a more intelligent way of doing this, but this should be able to
    handle the multiple layers of dependencies we're working with. 

    Args:
        args (Namespace object): User-provided arguments.

    """
    raft_cfg = load_raft_cfg()
    wf_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow')
    new_deps = 1
    while new_deps == 1:
        new_deps = 0
        mods = glob(pjoin(wf_dir, '**', '*.nf'), recursive=True)
        for mod in mods:
            base = mod.strip('.nf')
            deps = []
            with open(mod) as mfo:
                for line in mfo:
                    if re.search('^include.*nf.*', line):
                        dep = line.split()[-1].replace("'", '').split('/')[1]
                        if dep not in deps:
                            deps.append(dep)
        for dep in deps:
            curr_deps = [i.split('/')[-1] for i in glob(pjoin(wf_dir, '*'))]
            if dep not in curr_deps:
                new_deps = 1
                spoofed_args = args
                spoofed_args.module = dep
                load_module(spoofed_args)


def list_steps(args):
    """
    List the process and workflows available from a Nextflow component.
    Requires project since it assumes users may modify componenets in a
    project-specific manner.

    Args:
       args (Namespace object): User-provided arguments
    """
    raft_cfg = load_raft_cfg()

    glob_term = '*/'
    if args.module:
        glob_term = args.module + '/'

    globbed_mods = glob(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow', glob_term))
    for mod in globbed_mods:
        with open(pjoin(mod, mod.split('/')[-2] + '.nf')) as fo:
            for line in fo:
                if re.search('^workflow', line):
                    comment = "module: {}\ntype: workflow\nstep: {}\n".format(mod.split('/')[-2], line.split(' ')[1])
                elif re.search('^process', line):
                    comment = "module: {}\ntype: process\nstep: {}\n".format(mod.split('/')[-2], line.split(' ')[1])


def get_module_branch(args):
    """
    """
    branch = 'main'
    if re.search(':', args.branches):
        branch_lookup = {}
        arged_branches = args.branches.split(',')
        for combination in arged_branches:
            combo_mod, combo_branch = combination.split(':')
            branch_lookup[combo_mod] = combo_branch
        if args.module in branch_lookup.keys():
            branch = branch_lookup[args.module]
    else:
        branch = args.branches
    return branch


def load_module(args):
    """
    Part of the load-module mode.

    Loads a Nextflow module into a project's workflow directory.
    Allows users to specify a specific branch to checkout.
    Automatically loads 'main' branch of module's repo unless specified by user.

    Args:
        args (Namespace object): User-provided arguments.
    """
    raft_cfg = load_raft_cfg()
    if not args.repo:
        args.repo = raft_cfg['nextflow_repos']['nextflow_modules']
    # Should probably check here and see if the specified project even exists...
    workflow_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow')

    branch = get_module_branch(args)

    print("Loading module {} (branch {}) into project {}".format(args.module, branch, args.project_id))

    if not glob(pjoin(workflow_dir, args.module)):
        found = 0
        for subgroup in raft_cfg['nextflow_subgroups']["nextflow_module_subgroups"]:
            try:
                Repo.clone_from(pjoin(args.repo, subgroup, args.module),
                                pjoin(workflow_dir, args.module),
                                branch=branch)
                time.sleep(args.delay)
                found = 1
            except:
                pass
        if not found:
            sys.exit("/ ! \\ ERROR: Could not find module {} in any subgroups specified in RAFT config / ! \\".format(args.module))
        nf_cfg = pjoin(raft_cfg['filesystem']['projects'],
                       args.project_id,
                       'workflow',
                       'nextflow.config')
        mod_cfg = pjoin(raft_cfg['filesystem']['projects'],
                        args.project_id,
                        'workflow',
                        args.module,
                        args.module + '.config')
        if os.path.isfile(mod_cfg):
            update_nf_cfg(nf_cfg, mod_cfg)
    else:
        print("Module {} is already loaded into project {}. Skipping...".format(args.module, args.project_id))
    recurs_load_modules(args)


#def run_auto(args):
#    """
#    Given a loaded project, run auto.raft steps. This is a bit dangerous since
#    malicious code could be implanted into an auto.raft file, but can be made
#    safer by ensuring all commands are called through RAFT (in other words,
#    ensure steps are valid RAFT modes before running).
#
#    There are other considerations -- sometimes metadata may already be within
#    the metadata directory, so they won't need to be loaded a second time.
#    Perhaps this should be part of load-metadata?
#    """
#    raft_cfg = load_raft_cfg() 
#    auto_raft = pjoin(raft_cfg['filesystem']['projects'],



def run_workflow(args):
    """
    Part of the run-workflow mode.

    Runs a specified workflow on a user-specific set of sample(s), for all
    samples in manifest csv file(s), or both. Executes checked out branch of
    workflow unless specificed by user.

    Args:
        args (Namespace object): User-provided arguments.
    """
    raft_cfg = load_raft_cfg()
    init_dir = getcwd()
    all_samp_ids = []
    processed_samp_ids = []


    if not args.keep_previous_outputs:
        # Check for directory instead of try/except.
        try:
            shutil.rmtree(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'outputs'))
        except:
            pass

    # Getting base command
    nf_cmd = get_base_nf_cmd(args)

    # Appending work directory
    work_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'work')
    nf_cmd = add_nf_work_dir(work_dir, nf_cmd)

    # Appending global FASTQ directory (for internal FASTQ symlinking)
    nf_cmd = add_global_fq_dir(nf_cmd)

    # Appending global shared outputs directory
    nf_cmd = add_global_shared_dir(nf_cmd)


    os.chdir(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'logs'))
    print("Running:\n{}".format(nf_cmd))
    nf_exit_code = subprocess.run(nf_cmd, shell=True, check=False)
    if not nf_exit_code.returncode:
        print("Workflow completed!\n")
        if not args.no_reports:
            print("Moving reports to {}\n".format(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'outputs', 'reports')))
            reports = ['report.html', 'timeline.html', 'dag.dot', 'trace.txt']
            os.makedirs(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'outputs', 'reports'))
            for report in reports:
                if os.path.exists(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'logs', report)):
                    shutil.move(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'logs', report),
                                pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'outputs', 'reports', report))


def get_work_dirs(args):
    """
    Get all work dirs associated with the latest run of the project."
    """
    raft_cfg = load_raft_cfg()
    work_dirs = []
    log_dir = pjoin(raft_cfg['filesystem']['projects'],
                    args.project_id, 'logs')
    project_uuid = ''
    with open(pjoin(log_dir, '.nextflow', 'history')) as fo:
        for line in reversed(fo.read().split('\n')):
            if line:
                line = line.split('\t')
                if line[3] == 'OK':
                    project_uuid = line[5]
                    break
    os.chdir(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'logs'))
    work_dirs = [x for x in subprocess.run('nextflow log {}'.format(project_uuid), shell=True, check=False, capture_output=True).stdout.decode("utf-8").split('\n') if os.path.isdir(x)]
    return work_dirs


def get_size(start_path = '.'):
    """
    https://stackoverflow.com/a/1392549
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size


def add_global_fq_dir(samp_nf_cmd):
    """
    Part of run-workflow mode.

    Appends global fastq directory to Nextflow command.

    Args:
        samp_nf_cmd (str): Sample-specific Nextflow command.

    Returns:
        Str containing the modified Nextflow command with a working directory.
    """
    raft_cfg = load_raft_cfg()
    global_fq_dir = raft_cfg['filesystem']['fastqs']
    return ' '.join([samp_nf_cmd, '--global_fq_dir {}'.format(global_fq_dir)])


def add_global_shared_dir(samp_nf_cmd):
    """
    Part of run-workflow mode.

    Appends global fastq directory to Nextflow command.

    Args:
        samp_nf_cmd (str): Sample-specific Nextflow command.

    Returns:
        Str containing the modified Nextflow command with a working directory.
    """
    raft_cfg = load_raft_cfg()
    shared_dir = raft_cfg['filesystem']['shared']
    return ' '.join([samp_nf_cmd, '--shared_dir {}'.format(shared_dir)])


def add_nf_work_dir(work_dir, nf_cmd):
    """
    Part of run-workflow mode.

    Appends working directory to Nextflow command.

    Args:
        work_dir (str): Work directory path to be appended.
        nf_cmd (str): Nextflow command.

    Returns:
        Str containing the modified Nextflow command with a working directory.
    """
    return ' '.join([nf_cmd, '-w {}'.format(work_dir)])


def get_base_nf_cmd(args):
    """
    Part of run-workflow mode.

    Prepends the actual Nextflow execution portion to Nextflow command prior to
    execution. This currently globs for a *.nf file within the specified
    workflow directory (so workflow Nextflow files do NOT have to be named the
    same as the workflow repo).

    Args:
        args (Namespace object): User-specific arguments.
        samp_nf_cmd (str): Nextflow command.

    Returns:
        Str containing modified Nextflow command with execution portion.
    """
    raft_cfg = load_raft_cfg()

    # Processing nf-params
    cmd = []
    if args.nf_params:
        cmd = args.nf_params.split(' ')
    new_cmd = []
    # Should this be in its own additional function?
    for component in cmd:
        # Do any processing here.
        new_cmd.append(component)

    #Discovering workflow script
    workflow_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow')
    #Ensure only one nf is discoverd here! If more than one is discovered, then should multiple be run?
    discovered_nf = glob(pjoin(workflow_dir, 'main.nf'))[0]

    # Adding project directory
    proj_dir_str = ''
    if not re.search('--project_dir', args.nf_params):
        proj_dir = pjoin(raft_cfg['filesystem']['projects'], args.project_id)
        proj_dir_str = "--project_dir {}".format(proj_dir)

    # Adding all components to make base command.
    resume = ''
    reports = ''
    if not args.no_resume:
        resume = '-resume'
    if not args.no_reports:
        reports = '-with-trace -with-report -with-dag -with-timeline'
    cmd = ' '.join(['nextflow -Dnxf.pool.type=sync run', discovered_nf, ' '.join(new_cmd), proj_dir_str, resume, reports])
    return cmd


def update_nf_cfg(nf_cfg, mod_cfg):
    """
    Part of load-module mode.

    Updates the project-specific nextflow.config file with information from a
    specific module's config file (named <module>.config).

    This is currently designed to only pull in configuration parameters if they
    are not already in the nextflow.config. This is a blind spot that should be
    addressed in the future.

    Args:
        nf_cfg (str): Path to nextflow.config to be updated.
        comp_cfg (str): Path to component config file to use for updating nextflow.config.
    """
    new_nf_cfg = []
    lines_to_copy = []
    with open(mod_cfg) as mfo:
        for line in mfo:
            if line not in ["process {\n", "}\n"]:
                lines_to_copy.append(line)

    with open(nf_cfg) as nfo:
        for line in nfo:
            new_nf_cfg.append(line)
            if line == "process {\n":
                new_nf_cfg.extend(lines_to_copy)

    with open(nf_cfg, 'w') as nfo:
        for line in new_nf_cfg:
            nfo.write(line)


def rndm_str_gen(k=5):
    """
    Creates a random k-mer.
    """
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(k))


def load_raft_cfg():
    """ Part of several modes.

    This function reads the RAFT configuration file and provides a dictionary
    with configuration information.

    Returns:
        Dictionary with configuration information.
    """
    cfg = {}
    cfg_path = pjoin(getcwd(), '.raft.cfg')
    with open(cfg_path) as fo:
        cfg = json.load(fo)
    return cfg


def dump_to_auto_raft(args):
    """
    Part of several modes.

    Called anytime RAFT is called with non-administrative commands. This copies
    commands to auto.raft file.

    Args:
        args (Namespace object): User-specified arguments.
    """
    if args.command and args.command not in ['init-project', 'run-auto', 'package-project',
                                             'load-project', 'setup', 'push-project',
                                             'rename-project', 'run-workflow', 'copy-parameters']:
        raft_cfg = load_raft_cfg()
        auto_raft_path = pjoin(raft_cfg['filesystem']['projects'],
                               args.project_id,
                               '.raft',
                               'auto.raft')
        comment_out = ''
        if args.command in ['add-step']:
            comment_out = '#'
        with open(auto_raft_path, 'a') as fo:
            fo.write("{}{}\n".format(comment_out, ' '.join(sys.argv)))


def snapshot_postproc(inf, outf):
    """
    Strips out repeated steps from snapshot so auto-run can run as expected.

    This may be overly aggressive, but can modify it later.
    """
    with open(outf, 'w') as ofo:
        with open(inf) as ifo:
            new_contents = []
            contents = ifo.readlines()
            for line_idx, line in enumerate(contents):
                if not re.search("run-workflow", line):
                    new_contents.append(line)
                elif line_idx == len(contents) - 1:
                    line = line.strip().replace('n=', 'n="')
                    #print(line)
                    if re.search('-profile', line):
                        spl = line.split(' ')
                        ind =  [i for i, word in enumerate(spl) if re.search('-profile', word)]
                        spl[ind[0] + 1] = "RAFT_PROFILE_PLACEHOLDER"
                        line = ' '.join(spl)
                new_contents.append(line + '"\n')
            for line in new_contents:
                ofo.write(line)


def package_project(args):
    """
    Part of package-project mode.
    """
    raft_cfg = load_raft_cfg()
    proj_dir = os.path.join(raft_cfg['filesystem']['projects'], args.project_id)
    foo = rndm_str_gen()
    proj_tmp_dir = os.path.join(raft_cfg['filesystem']['projects'], args.project_id, 'tmp', foo)

    os.mkdir(proj_tmp_dir)

    # Copying metadata directory. Should probably perform some size checks here.
    os.mkdir(pjoin(proj_tmp_dir, 'metadata'))
    metadata_files = glob(pjoin(proj_dir, 'metadata', '**'), recursive=True)
    for mfile in metadata_files:
        mfilel = mfile.split('/')
        msuffix = '/'.join(mfilel[mfilel.index('metadata')+1:])
        if not os.path.islink(mfile) and not os.path.isdir(mfile):
            basedir = pjoin(proj_tmp_dir, 'metadata', os.path.dirname(msuffix))
            if '/' in msuffix:
                os.makedirs(pjoin(proj_tmp_dir, 'metadata', os.path.dirname(msuffix)))
            shutil.copyfile(mfile, pjoin(proj_tmp_dir, 'metadata', msuffix))

    # Getting required checksums. Currently only doing /datasets, but should
    # probably do other directories produced by workflow as well.
    dirs = ['outputs', 'metadata', 'fastqs', 'references', 'indices', 'workflow']
    if not args.no_checksums:
        hashes = {}
        with open(pjoin(proj_tmp_dir, 'checksums'), 'w') as fo:
            hashes = {}
            for dir in dirs:
                files = glob(pjoin('projects', args.project_id, dir, '**'), recursive=True)
                sub_hashes = {file: md5(file) for file in files if os.path.isfile(file)}
                hashes.update(sub_hashes)
            json.dump(hashes, fo, indent=4)

    # Get Nextflow configs, etc.
    os.mkdir(pjoin(proj_tmp_dir, 'workflow'))
    wf_dirs = glob(pjoin(proj_dir, 'workflow', '*'))
    igpat = ''
    if args.no_git:
        igpat = '.*'
    for dir in wf_dirs:
        if os.path.isdir(dir):
            shutil.copytree(dir,
                            pjoin(proj_tmp_dir, 'workflow', os.path.basename(dir)),
                            ignore=shutil.ignore_patterns(igpat))
        else:
            shutil.copyfile(dir,
                            pjoin(proj_tmp_dir, 'workflow', os.path.basename(dir)))

    # Get auto.raft
    shutil.copyfile(pjoin(proj_dir, '.raft', 'auto.raft'),
                    pjoin(proj_dir, '.raft', 'snapshot.raft.actual'))
    snapshot_postproc(pjoin(proj_dir, '.raft', 'snapshot.raft.actual'),
                      pjoin(proj_dir, '.raft', 'snapshot.raft.postproc'))

    shutil.copyfile(pjoin(proj_dir, '.raft', 'snapshot.raft.postproc'),
                    pjoin(proj_tmp_dir, 'snapshot.raft'))
    shutil.copyfile(pjoin(proj_dir, '.raft', 'snapshot.raft.actual'),
                    pjoin(proj_tmp_dir, 'snapshot.raft.actual'))

    rftpkg = ''
    if args.output:
        rftpkg = pjoin(proj_dir, 'rftpkgs', args.output + '.rftpkg')
    else:
        rftpkg = pjoin(proj_dir, 'rftpkgs', 'default.rftpkg')
    with tarfile.open(rftpkg, 'w') as taro:
        for i in os.listdir(proj_tmp_dir):
            #print(i)
            taro.add(os.path.join(proj_tmp_dir, i), arcname = i)


def md5(fname):
#https://stackoverflow.com/a/3431838
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def load_project(args):
    """
    Part of load-project mode.
    """
    raft_cfg = load_raft_cfg()
    # Should really be using .init.cfg from package here...
    fixt_args = {'init_config': os.path.join(os.getcwd(), '.init.cfg'),
                 'project_id': args.project_id,
                 'repo_url': ''}
    fixt_args = argparse.Namespace(**fixt_args)

    # Initialize project
    init_project(fixt_args)
    # Moving mounts.config so that can be protected and reintroduced after copying over workflow.config.
    shutil.move(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow', 'mounts.config'),
                pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.mounts.config'))

    tarball = ''
    if args.rftpkg:
        # Copy rftpkg into project
        shutil.copyfile(args.rftpkg,
                        pjoin(raft_cfg['filesystem']['projects'],
                              args.project_id,
                              'rftpkgs',
                              os.path.basename(args.rftpkg)))
    elif args.repo_url:
        repo = Repo(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'rftpkgs'))
        repo.create_remote('origin', args.repo_url)
        repo.git.pull('origin', args.branch)

    tarball = pjoin(raft_cfg['filesystem']['projects'],
                    args.project_id,
                    'rftpkgs',
                    os.path.basename(args.rftpkg))

    # Extract and distribute tarball contents
    tar = tarfile.open(tarball)
    tar.extractall(os.path.join(raft_cfg['filesystem']['projects'], args.project_id, '.raft'))
    tar.close()

    for dir in ['metadata', 'workflow']:
        shutil.rmtree(pjoin(raft_cfg['filesystem']['projects'], args.project_id, dir))
        shutil.copytree(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', dir),
                        pjoin(raft_cfg['filesystem']['projects'], args.project_id, dir))
    shutil.move(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow', 'mounts.config'),
                pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow', '.mounts.config.orig'))
    shutil.move(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.mounts.config'),
                pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'workflow', 'mounts.config'))

    # Create back-up of snapshot.raft and checksums

    if os.path.isfile(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'checksums')):
        shutil.copyfile(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'checksums'),
                        pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'checksums.orig'))

        replace_proj_id(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'checksums'),
                              get_orig_prod_id(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'snapshot.raft.orig')),
                              args.project_id)
    else:
        print("Checksums file not found within RFTPKG. Checksums cannot be checked.")


    shutil.copyfile(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'snapshot.raft'),
                    pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'snapshot.raft.orig'))

    orig_proj_id = get_orig_prod_id(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'snapshot.raft'))

    replace_proj_id(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'snapshot.raft'), get_orig_prod_id(pjoin(raft_cfg['filesystem']['projects'], args.project_id, '.raft', 'snapshot.raft.orig')), args.project_id)


def replace_proj_id(fle, old_proj_id, new_proj_id):
    """
    """
    raft_cfg = load_raft_cfg()
    with open(pjoin(raft_cfg['filesystem']['projects'], new_proj_id, 'tmp', 'tmp_file'), 'w') as tfo:
        with open(fle) as fo:
            contents = fo.readlines()
            for line in contents:
                line = line.replace('-p {}'.format(old_proj_id), '-p {}'.format(new_proj_id))
                line = line.replace('projects/{}'.format(old_proj_id), 'projects/{}'.format(new_proj_id))
                tfo.write(line)

    shutil.move(pjoin(raft_cfg['filesystem']['projects'], new_proj_id, 'tmp', 'tmp_file'), fle)


def get_orig_prod_id(fle):
    """
    """
    with open(fle) as fo:
        contents = fo.readlines()
        first = contents[0].strip()
        ind = ''
        ind = first.split(' ').index('-p')
        if not ind:
            ind = first.split(' ').index('--project-id')
        return first.split(' ')[ind+1]


def get_params_from_module(module_path):
    """
    """
    undef_params, defined_params = ([], [])
    with open(module_path) as mfo:
        for line in mfo.readlines():
            line = line.rstrip()
            if re.search("^params.*", line):
                if re.search(" = ''", line):
                    undef_params.append(line.partition(' ')[0])
                else:
                    defined_params.append(line.partition(' ')[0])

    return undef_params, defined_params


def get_section_insert_idx(contents, section, stop='\n'):
    """
    Part of add-step mode.

    Find the index of the nearest empty row for a section. Basically, find
    where the the a set of rows should be inserted within a main.nf specific
    section.
    """
    start = contents.index(section)
    insert_idx = contents[start:].index(stop)
    return start + insert_idx


def get_wf_mod_map(args):
    """
    """
    raft_cfg = load_raft_cfg()
    wf_mod_map = {}
    nf_scripts = glob(pjoin(raft_cfg['filesystem']['projects'],
                            args.project_id,
                            'workflow',
                            '*/*.nf'))
    for nf_script in nf_scripts:
        wfs = extract_wfs_from_script(nf_script)
        for wf in wfs:
            wf_mod_map[wf] = nf_script

    return wf_mod_map


def extract_wfs_from_script(script_path):
    """
    """
    wfs = []
    with open(script_path) as spo:
        for line in spo:
            if re.search('^workflow', line):
                wfs.append(line.replace('workflow ', '').split('{')[0].strip())
    return wfs


def add_step(args):
    """
    Part of add-step mode.

    Args:
        args (Namespace object): User-provided arguments.
    """
    raft_cfg = load_raft_cfg()
    # Relevant files
    main_nf = pjoin(raft_cfg['filesystem']['projects'],
                    args.project_id,
                    'workflow',
                    'main.nf')
    mod_nf = pjoin(raft_cfg['filesystem']['projects'],
                   args.project_id,
                   'workflow',
                   args.module,
                   args.module + '.nf')

    # Load main.nf contents
    main_contents = []
    with open(main_nf) as mfo:
        main_contents = mfo.readlines()

    print("Making backup of project's main.nf...")
    shutil.copyfile(main_nf, main_nf + '.bak')

    # Step's inclusion statement for main.nf
    if args.alias:
        inclusion_str = "include {{ {step} as {alias} }} from './{mod}/{mod}.nf'\n".format(step=args.step, mod=args.module, alias=args.alias)
    else:
        inclusion_str = "include {{ {step} }} from './{mod}/{mod}.nf'\n".format(step=args.step, mod=args.module)

    # Need to load main.nf params here to check against when getting step-specific params.
    # Seems odd to emit the undefined and defined separately.
    main_undef_params, main_defined_params = get_params_from_module(main_nf)
    main_params = main_undef_params + main_defined_params

    # Extract step contents from step's module file in order to make string to
    # put within main.nf
    step_str = ''
    step_slice = extract_step_slice_from_nfscript(mod_nf, args.step)
    if not step_slice:
        sys.exit("ERROR: Step {} could not be found in module {}.".format(args.step, args.module))
    step_str = get_workflow_str(step_slice)
    if args.alias:
        params = step_str.partition('(')[2]
        step_str = ''.join([args.alias, '(', params])
    print("Adding the following step to main.nf: {}".format(step_str.rstrip()))

    # Parameterization
    wf_mod_map = get_wf_mod_map(args)
    final_steps = []
    discod_steps = [args.step]
    while discod_steps:
        new_round_steps = []
        for step in discod_steps:
            step_slice = extract_step_slice_from_nfscript(wf_mod_map[step], step)
            new_round_steps.extend([i.partition('(')[0] for i in step_slice if i.partition('(')[0] in wf_mod_map.keys()])
            discod_steps.remove(step)
            final_steps.append(step)
        discod_steps.extend(new_round_steps)

    all_step_params = []
    for step in final_steps:
        step_slice = extract_step_slice_from_nfscript(wf_mod_map[step], step)
        if step == args.step:
            all_step_params.extend(extract_params_from_contents(step_slice, False))
        else:
            all_step_params.extend(extract_params_from_contents(step_slice, True))

    expanded_params = expand_params(all_step_params)
    filted_expanded_params = {}
    for k,v in expanded_params.items():
        if k not in main_params and k != 'params.':
            filted_expanded_params[k] = v

    expanded_params = filted_expanded_params

    expanded_undef_params = '\n'.join(["{} = {}".format(k, expanded_params[k]) for k in
                            sorted(expanded_params.keys()) if expanded_params[k] == "''"]) + '\n'
    expanded_defined_params = '\n'.join(["{} = {}".format(k, expanded_params[k]) for k in
                                                          sorted(expanded_params,
                                                          key = lambda i: (i.split('$')[-1], len(i.split('$')))) if
                                                          expanded_params[k] != "''"]) + '\n'

    # Applying changes to main.nf
    if step_str not in main_contents and inclusion_str not in main_contents:

        inc_idx = get_section_insert_idx(main_contents, "/*Inclusions*/\n")
        main_contents.insert(inc_idx, inclusion_str)

        gen_params_idx = get_section_insert_idx(main_contents, "/*General Parameters*/\n")
        main_contents.insert(gen_params_idx, expanded_undef_params)

        fine_params_idx = get_section_insert_idx(main_contents, "/*Fine-tuned Parameters*/\n")
        main_contents.insert(fine_params_idx, expanded_defined_params)

        wf_idx = get_section_insert_idx(main_contents, "workflow {\n", "}\n")
        main_contents.insert(wf_idx, step_str.replace('(', '(\n  ').replace(', ', ',\n  '))


        with open(main_nf, 'w') as ofo:
            ofo.write(''.join(main_contents))
    else:
        print("/ ! \\ ERROR! / ! \\")
        print("Step {} has already been added to Project {}.".format(step_str.split('(')[0], args.project_id))
        print("Please use step aliasing (-a/--alias) if you intend to use this step multiple times.")
        sys.exit(1)


def expand_params(params):
    """
    Part of add-step mode.

    Expand the parameters such that each tier is explicitly and separately
    defined. This is provides the ability for multiple tiers of parameter
    definition within the main.nf script.

    For example, given parameters [params.foo.bar.tool, params.foo.bat.tool]
    (where the same tool is being called in two different contexts), then
    expand_params() will generate:
    params.tool = ''
    params.foo$tool = params.tool
    params.foo$bar$tool = params.foo.tool
    params.foo$bat$tool = params.foo.tool

    Notice the user can provide a global tool parameter that is effectively
    inherited down the entire heirarchy. This allows the user to define a
    single parameter set if that's suitable for the situation. Alternatively
    they can define a parameter set at the level of params.foo.tool (which will
    be inherited by params.foo.bar.tool and params.foo.bat.tool, but not other
    instances of tool not under the foo namespace). Users may also set the
    parameter set at each instance of the tool.

    Args:
        params (list): List of params to be expanded.

    Returns:
        extended_params (dict): Dictionary containing parameters as keys and
                                parameter definitions as values.
    """
    expanded_params = {}
    for param in params:
        param = param.partition('.')[2]
        param = param.split('$')
        expanded_params['params.' + '$'.join(param)] = "''"
        if len(param) > 1:
            for i in range(0,len(param) - 1):
                expanded_params['params.' + '$'.join(param[:i+1] + [param[-1]])] = 'params.' + '$'.join(param[:i] + [param[-1]])
            expanded_params['params.' + param[-1]] = "''"
    return expanded_params


def is_workflow(step):
    """
    Part of add-step mode.

    Determine if a step is a workflow.

    Args:
        contents (list): List containing the contents of a module/component in
                         which step is defined.
        step (str): Step being queried. This string may be associated with a process or a workflow.

    Returns:
        True if step is a workflow, otherwise False.
    """
    is_workflow = False
    if re.search('workflow', step[0]):
        is_workflow = True
    return is_workflow


def find_step_module(contents, step):
    """
    Part of add-step mode.

    Find a step's module based on the contents of the module in which it's being called. This is effectively parsing 'include' statements.

    Args:
        contents (list): List containing rows from a Nextflow module/component.
        step (str): Step that requires parent component.

    Returns:
        Str containing parent component for step.
    """
    mod = []
    try:
        mod = [re.findall('include .*{}.*'.format(step), i) for i in contents if re.findall('include .*{}.*'.format(step), i)][0][0].split('/')[1]
    except FileNotFoundError:
        pass
    return mod


def find_step_actual_and_alias(contents, step):
    """
    Part of add-step mode.

    Find a step's module based on the contents of the module in which it's being called. This is effectively parsing 'include' statements.

    Args:
        contents (list): List containing rows from a Nextflow module/component.
        step (str): Step that requires parent component.

    Returns:
        Str containing parent component for step.
    """
    mod = []

    mod = [re.findall('include .*{}.*'.format(step), i) for i in contents if re.findall('include .*{}.*'.format(step), i)][0][0]
    if not re.findall(' as ', mod):
        actual = step
        alias = ''
    else:
        mod = mod.split('{')[1].split('}')[0]
        mod = mod.partition(' as ')
        actual = mod[0].strip()
        alias = mod[2].strip()
    return(actual, alias)


def extract_steps_from_contents(contents):
    """
    Part of add-step mode.

    Get list of (sub)steps (workflows/processes) being called from contents.
    NOTE: Contents in this case means a single workflow's contents.

    Args:
        contents (list): List containing the rows from a workflow's entry in a component.
    """
    wfs = [re.findall('^[\w_]+\(.*', i) for i in contents if re.findall('^[\w_]+\(.*', i)]
    flat = [i.partition('(')[0] for j in wfs for i in j]
    return(flat)


def extract_params_from_contents(contents, discard_requires):
    """
    Part of add-step mode.

    Get list of params being used from contents.
    NOTE: Contents in this case means a single step's contents.

    Args:
        contents (list): List containing the rows from a workflow's entry in a component.
    """
    require_params = []
    if [re.findall("// require:", i) for i in contents if re.findall("// require:", i) for i in contents]:
        start = contents.index("// require:") + 1
        end = contents.index("take:")
        require_params = [i.replace('//   ','').split(',')[0] for i in contents[start:end] if re.search('^//   params', i)]
    params = [re.findall("(params.*?,|params.*?\)|params.*\?})", i) for i in contents if
              re.findall("params.*,|params.*\)", i) and i != 'params.']
    flat = [i.partition('/')[0].replace(',','').replace(')', '').replace('}', '').replace("'", '').replace('"', '').replace('/', '').replace('\\', '') for
            j in params for i in j]
    # THIS IS TOO RESTRICTIVE!!! This should only be applied if it's not the initial step being called.
    if discard_requires:
        flat = [i for i in flat if i not in require_params]
    else:
        flat = flat + require_params
    return(flat)


def extract_step_slice_from_nfscript(nfscript_path, step):
    """
    Part of add-step mode.

    Extract a step's contents (for parameter and wf_extraction) from a
    module file's conents.

    Args:
        contents (list): List containing the contents of a module file.
        step (str): Step of interest.
    """
    step_slice = []
    contents = []
    with open(nfscript_path) as fo:
        contents = [i.strip() for i in fo.readlines()]
    # Need the ability to error out if step doesn't exist. Should list steps
    # from module in that case.
    try:
        step_start = contents.index("workflow {} {{".format(step))
        step_end = contents.index("}", step_start)
        step_slice = contents[step_start:step_end]
    except:
        pass
    return step_slice



def get_workflow_str(wf_slice):
    """
    Part of add-step mode.

    Get the string containing a workflow and its parameters for the main.nf workflow.

    Note: This seems like a pretty fragile system for extracting strings.
    """
    # Can just strip contents before processing to not have to deal with a lot
    # of the newlines and space considerations.
    wf_list = []
    if '// require:' in wf_slice:
        require_idx = wf_slice.index('// require:')
        take_idx = wf_slice.index('take:')
        wf_list = [wf_slice[0].replace("workflow ", "").replace(" {",""), '(',
                   ", ".join([x.replace('//  ', '').strip() for x in wf_slice[require_idx+1:take_idx]]), ')\n']
    else:
        wf_list = [wf_slice[0].replace("workflow ", "").replace(" {", ""), '()\n']
    wf_str = "".join(wf_list)
    return wf_str


def get_process_str(proc_slice):
    """
    Part of add-step mode.

    Get the string containing a process and its parameters for the main.nf workflow.
    """
    stop_idx = ''
    start_idx = proc_slice.index('input:')
    if 'output:' in proc_slice:
        stop_idx = proc_slice.index('output:')
    else:
        stop_idx = proc_slice.index('script:')
    params = [x for x in proc_slice[start_idx+1:stop_idx] if x]
    cleaned_params = []
    for param in params:
        param = param.partition(' ')
        if param[0] in ['tuple', 'set']:
            cleaned_params.append(''.join(['{', param[2], '}']))
        else:
            cleaned_params.append(param[2])

    proc_list = [proc_slice[0].replace('process ', '').replace(' {', ''), '(', ', '.join(cleaned_params), ')\n']
    proc_str = ''.join(proc_list)
    return proc_str


def push_project(args):
    """
    """
    raft_cfg = load_raft_cfg()
    local_repo = pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'repo')
    shutil.copyfile(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'rftpkgs', args.rftpkg + '.rftpkg'),
                    pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'repo', args.rftpkg + '.rftpkg'))
    repo = Repo(local_repo)
    repo.index.add(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'repo', args.rftpkg + '.rftpkg'))
    repo.index.commit("rftpkg commit {}".format(time.time()))
    repo.git.push('origin', repo.head.ref)


def chk_proj_id_exists(project_id):
    """
    """
    raft_cfg = load_raft_cfg()
    if not os.path.isdir(pjoin(raft_cfg['filesystem']['projects'], project_id)):
        sys.exit("Check your project identifier (-p/--project-id). Project {} cannot be found in {}"
                 .format(project_id, raft_cfg['filesystem']['projects']))


def update_modules(args):
    """
    """
    raft_cfg = load_raft_cfg()
    main_nf = pjoin(raft_cfg['filesystem']['projects'],
                    args.project_id,
                    'workflow')
    for mod in glob(pjoin(main_nf, '*', '')):
        if os.path.basename(os.path.dirname(mod)) in args.modules.split(',') or not args.modules:
            repo = Repo(mod)
            ori = repo.remotes.origin
            mod_dir = os.path.basename(os.path.dirname(mod))
            print(f"Pulling latest for module {mod_dir} (branch {repo.active_branch.name})")
            ori.pull()


def rename_project(args):
    """
    """
    raft_cfg = load_raft_cfg()
    proj_dir = pjoin(raft_cfg['filesystem']['projects'],
                     args.project_id)
    for f in [pjoin('workflow', 'mounts.config'),
              pjoin('workflow', 'nextflow.config'),
              pjoin('.raft', 'auto.raft')]:
        shutil.move(pjoin(proj_dir, f), pjoin(proj_dir, f + '.rename.bak'))
        with open(pjoin(proj_dir, f), 'w') as fo:
            with open(pjoin(proj_dir, f + '.rename.bak')) as io:
                for line in io.readlines():
                    fo.write(line.replace(args.project_id, args.new_id))
    shutil.move(proj_dir,
                pjoin(raft_cfg['filesystem']['projects'], args.new_id))


def clean_project(args):
    """
    """
    raft_cfg = load_raft_cfg()
    log_dir = pjoin(raft_cfg['filesystem']['projects'],
                    args.project_id, 'logs')
    successful_run = ''
    project_uuid = ''
    with open(pjoin(log_dir, '.nextflow', 'history')) as fo:
        for line in reversed(fo.read().split('\n')):
            if line:
                line = line.split('\t')
                if line[3] == 'OK':
                    successful_run = line[2]
                    project_uuid = line[5]
                    break
    print("Project UUID is: {}".format(project_uuid))
    print("Last successful run is: {}".format(successful_run))
    os.chdir(pjoin(raft_cfg['filesystem']['projects'], args.project_id, 'logs'))
    all_work_hashes = [x for x in subprocess.run('nextflow log {}'.format(project_uuid), shell=True, check=False, capture_output=True).stdout.decode("utf-8").split('\n') if os.path.isdir(x)]
    successful_work_hashes = [x for x in subprocess.run("nextflow log -f 'workdir, status' {} | grep -E 'COMPLETED|CACHED' | cut -f 1 -d '	'".format(successful_run), shell=True, check=False, capture_output=True).stdout.decode("utf-8").split('\n') if x in all_work_hashes]
    completed_work_hashes = [x for x in subprocess.run("nextflow log -f 'workdir, status' {} | grep -E 'COMPLETED|CACHED' | cut -f 1 -d '	'".format(project_uuid), shell=True, check=False, capture_output=True).stdout.decode("utf-8").split('\n') if x in all_work_hashes]
    print("All run work hashes count: {}".format(len(all_work_hashes)))
    print("Successful run work hashes count: {} ".format(len(successful_work_hashes)))
    print("Completed run work hashes count: {} ".format(len(completed_work_hashes)))
    cleanable_hashes = []
    if args.keep_latest and input("This will only keep work directories from the latest successful run!\nAre you sure? ") in ['YES', 'yes', 'Yes', 'Y', 'y']:
        cleanable_hashes = [x for x in all_work_hashes if x not in successful_work_hashes]
    else:
        cleanable_hashes = [x for x in all_work_hashes if x not in completed_work_hashes]
    print("Cleanable run work hashes count: {}".format(len(cleanable_hashes)))
    if not args.no_exec:
        for cleanable_dir in cleanable_hashes:
            print(f"Removing extra files from {cleanable_dir}...")
            cleanable_files = [i for i in os.listdir(cleanable_dir) if i not in ['meta'] and not re.search('command', i)]
            for cleanable_file in cleanable_files:
                try:
                    shutil.rmtree(cleanable_file)
                except FileNotFoundError:
                    pass
    else:
        print("Skipping deletion due to -n/--no-exec.")


def load_dataset(args):
    """
    Steps:
      - load all files from metadata/<args.dataset_id> into projects/<args.project_id>/metadata/<args.dataset_id>
      - add step t projects/<args.project_id>/workflow/main.nf with alias for prep_dataset as prep_<args.dataset_id>
    """
    raft_cfg = load_raft_cfg()
    args.module = args.dataset_id
    args.delay = 0
    load_module(args)
    dataset_files = [x.split('/')[-1] for x in glob(pjoin(raft_cfg['filesystem']['metadata'], args.dataset_id, '*'))]
    args.sub_dir = args.dataset_id
    for dataset_file in dataset_files:
        args.file = dataset_file
        print("Loading dataset file {}...".format(args.file))
        load_metadata(args)
    args.module = args.dataset_id
    args.step = 'prep_dataset'
    args.alias = 'prep_{}'.format(args.dataset_id)
    add_step(args)


def touch(path):
    """
    https://stackoverflow.com/a/12654798
    """
    with open(path, 'a'):
        os.utime(path, None)


def copy_parameters(args):
    """
    """
    src_proj_main = pjoin(raft_cfg['filesystem']['projects'], args.source_project, 'workflow', 'main.nf')
    orig_proj_main = pjoin(raft_cfg['filesystem']['projects'], args.destination_project, 'workflow', 'main.nf')
    new_proj_main = pjoin(raft_cfg['filesystem']['projects'], args.destination_project, 'workflow', 'main.nf.copy_params')

    raft_cfg = load_raft_cfg()
    source_params = {}
    if args.source_project:
        with open(src_proj_main) as fo:
            source_params = extract_params_from_proj_or_cfg(fo)
    elif args.source_config:
        with open(args.source_config) as fo:
            source_params = extract_params_from_proj_or_cfg(fo)

    with open(orig_proj_main) as dfo:
        with open(new_proj_main, 'w') as tfo:
            for line in dfo.readlines():
                parted_line = line.rstrip().partition(' = ')
                if parted_line[0] in source_params.keys() and source_params[parted_line[0]] != parted_line[2]:
                    tfo.write("{} = {}\n".format(parted_line[0], source_params[parted_line[0]]))
                else:
                    tfo.write(line)
    print("Done copying parameters.")


    print("Verify parameters in {} and".format(new_proj_main))
    print("copy {} to {} to complete.".format(new_proj_main, orig_proj_main))


def extract_params_from_proj_or_cfg(fo):
    """
    """
    source_params = {}
    # line conditions
    for line in fo.readlines():
        line = line.rstrip()
        if (line.startswith('params.') and
            not line.partition(' = ')[2].startswith('params') and
            not re.search('project_identifier', line)):
            line = line.partition(' = ')
            source_params[line[0]] = line[2]
    return source_params


def main():
    """
    """

    args = get_args()

    if 'project_id' in args and args.command not in ['init-project', 'load-project', 'copy-parameters']:
        chk_proj_id_exists(args.project_id)

    # Only dump to auto.raft if RAFT successfully completes.
    dump_to_auto_raft(args)

    # I'm pretty sure .setdefaults within subparsers should handle running
    # functions, but this will work for now.
    if args.command == 'setup':
        setup(args)
    elif args.command == 'init-project':
        init_project(args)
    elif args.command == 'load-manifest':
        load_manifest(args)
    elif args.command == 'load-metadata':
        load_metadata(args)
    elif args.command == 'load-reference':
        load_reference(args)
    elif args.command == 'load-module':
        raft_cfg = load_raft_cfg()
        print("NOTE: Module Nextflow configuration modifications must be performed in {}"
              .format(pjoin(raft_cfg['filesystem']['projects'], args.project_id,
                            'workflow', 'nextflow.config')))
        load_module(args)
    elif args.command == 'list-steps':
        list_steps(args)
    elif args.command == 'update-mounts':
        update_mounts(args)
    elif args.command == 'add-step':
        add_step(args)
    elif args.command == 'run-workflow':
        run_workflow(args)
#    elif args.command == 'run-auto':
#        run_auto(args)
    elif args.command == 'package-project':
        package_project(args)
    elif args.command == 'load-project':
        load_project(args)
    elif args.command == 'push-project':
        push_project(args)
    elif args.command == 'update-modules':
        update_modules(args)
    elif args.command == 'rename-project':
        rename_project(args)
    elif args.command == 'clean-project':
        clean_project(args)
    elif args.command == 'load-dataset':
        load_dataset(args)
    elif args.command == 'copy-parameters':
        copy_parameters(args)


if __name__ == '__main__':
    main()