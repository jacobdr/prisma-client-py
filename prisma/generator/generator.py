import logging
from pathlib import Path
from typing import Dict, Any
from contextvars import ContextVar
from distutils.dir_util import copy_tree

from jinja2 import Environment, PackageLoader

from .models import Data
from .utils import is_same_path
from .types import PartialModelFields


__all__ = ('run', 'BASE_PACKAGE_DIR', 'partial_models_ctx')

log = logging.getLogger(__name__)
BASE_PACKAGE_DIR = Path(__file__).parent.parent
DEFERRED_TEMPLATES = {'partials.py.jinja'}
partial_models_ctx: ContextVar[Dict[str, PartialModelFields]] = ContextVar(
    'partial_models_ctx', default={}
)


def run(params: Dict[str, Any]) -> None:
    params = vars(Data.parse_obj(params))
    rootdir = Path(params['generator'].output)
    if not rootdir.exists():
        rootdir.mkdir(parents=True, exist_ok=True)

    if not is_same_path(BASE_PACKAGE_DIR, rootdir):
        copy_tree(str(BASE_PACKAGE_DIR), str(rootdir))

    env = Environment(
        loader=PackageLoader('prisma.generator', 'templates'),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    for name in env.list_templates():
        if (
            not name.endswith('.py.jinja')
            or name.startswith('_')
            or name in DEFERRED_TEMPLATES
        ):
            continue

        render_template(env, rootdir, name, params)

    config = params['generator'].config
    if config.partial_type_generator:
        log.debug('Generating partial types')
        config.partial_type_generator.run()

    params['partial_models'] = partial_models_ctx.get()
    for name in DEFERRED_TEMPLATES:
        render_template(env, rootdir, name, params)

    log.debug('Finished generating the prisma python client')


def render_template(
    env: Environment, rootdir: Path, name: str, params: Dict[str, Any]
) -> None:
    template = env.get_template(name)
    output = template.render(**params)

    file = rootdir.joinpath(name.rstrip('.jinja'))
    if not file.parent.exists():
        file.parent.mkdir(parents=True, exist_ok=True)

    file.write_text(output)
    log.debug('Wrote generated code to %s', file.absolute())
