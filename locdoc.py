import os
import random
import shutil
import subprocess
import tempfile
import docker
import logging

from argparse import ArgumentParser
from os import path
from git import Repo
from shutil import move
from manifest import parse_manifest

_random = random.Random()
logger = logging.getLogger(__name__)


def run():
    logging.basicConfig(encoding="utf-8", level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s",
                        datefmt='%Y-%m-%d %H:%M:%S')

    parser = ArgumentParser(description="Local Docker Deployer")
    parser.add_argument("-m", "--manifest", required=True, help="path to deployment manifest file")
    args = parser.parse_args()

    manifest_props = parse_manifest(_random_str(), args.manifest)
    logger.info(manifest_props)

    tmpdir = tempfile.gettempdir()

    workdir = path.join(tmpdir, _random_str())
    logger.info(f"Creating workdir: {workdir}")

    logger.info("Cloning artifact repo")
    artifact_repo_dir = path.join(workdir, manifest_props["image"]["name"])
    os.makedirs(artifact_repo_dir)
    os.chdir(artifact_repo_dir)
    Repo.clone_from(manifest_props["artifact"]["repo"], ".", branch=manifest_props["artifact"]["tag"])

    config_repo_dir = path.join(artifact_repo_dir, manifest_props["config"]["destinationPath"])
    os.makedirs(config_repo_dir, exist_ok=True)

    logger.info("Cloning config repo")
    tmp_config_repo_dir = path.join(workdir, _random_str())
    os.makedirs(tmp_config_repo_dir)
    os.chdir(tmp_config_repo_dir)
    Repo.clone_from(manifest_props["config"]["repo"], ".", branch=manifest_props["config"]["tag"])

    logger.info("Merging config in artifact")
    tmp_files = os.listdir(tmp_config_repo_dir)
    for file in tmp_files:
        move(path.join(tmp_config_repo_dir, file), config_repo_dir)

    logger.info("Executing build command")
    os.chdir(artifact_repo_dir)
    subprocess.run(["bash", "-c", manifest_props["artifact"]["buildCmd"]])

    logger.info("Building Docker image")
    docker_cli = docker.from_env()
    docker_image = f"{manifest_props["image"]["name"]}:{manifest_props["image"]["version"]}"
    docker_file_path = path.join(artifact_repo_dir, manifest_props["artifact"]["dockerFile"])
    docker_cli.images.build(tag=docker_image, path=artifact_repo_dir, dockerfile=docker_file_path)

    docker_net = manifest_props["deploy"]["network"]
    if docker_net:
        networks = docker_cli.networks.list(names=[docker_net])
        if not networks:
            logger.info(f"Docker network '{docker_net}' not found, creating...")
            docker_cli.networks.create(docker_net)

    docker_container = manifest_props["deploy"]["name"]
    containers = docker_cli.containers.list(all=True, filters={"name": docker_container})
    if containers:
        container_id = containers[0].id
        logger.info(f"Existing container found: {container_id}")
        container_status = containers[0].status
        container = docker_cli.containers.get(container_id)
        if container_status == "running":
            logger.info(f"Stopping container '{docker_container}'")
            container.stop()
        logger.info(f"Removing existing container '{docker_container}'")
        container.remove(v=True)

    runflags = manifest_props["deploy"]["runFlags"]
    if "--network" not in runflags:
        runflags += f" --network {docker_net}"

    logger.info(f"Starting new docker container '{docker_container}'")
    # docker python SDK limitation fix: passing dynamic args to run cmd
    subprocess.run(["bash", "-c", f"docker run -d {runflags} --name {docker_container} {docker_image}"])

    docker_cli.api.prune_builds(all=True)

    logger.info(f"Removing workdir {workdir}")
    shutil.rmtree(workdir)

    logger.info("Done!")


def _random_str():
    return str(_random.randint(10000, 99999))
