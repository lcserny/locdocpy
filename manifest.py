import logging
from collections.abc import MutableMapping

from yaml import load, Loader
from mergedeep import merge

logger = logging.getLogger(__name__)


def parse_manifest(random_name, manifest_file) -> MutableMapping:
    logger.info(f"Parsing manifest: {manifest_file}")

    manifest_data = open(manifest_file, "r").read()
    logger.info(f"----- \n{manifest_data}")

    default_props = {
        "name": random_name,
        "artifact": {"tag": "master", "dockerFile": "Dockerfile"},
        "config": {"tag": "master"},
        "image": {"version": "1.0", "name": random_name + "-image"},
        "deploy": {"type": "container", "name": random_name}
    }
    loaded_props = load(manifest_data, Loader=Loader)
    props = merge(default_props, loaded_props)

    _validate(props)

    return props


def _validate(props):
    if not props["artifact"]["repo"]:
        raise Exception("manifest provided has no `artifact.repo`")

    if not props["artifact"]["buildCmd"]:
        raise Exception("manifest provided has no `artifact.buildCmd`")

    if not props["config"]["repo"]:
        raise Exception("manifest provided has no `config.repo`")

    if not props["config"]["destinationPath"]:
        raise Exception("manifest provided has no `config.destinationPath`")
