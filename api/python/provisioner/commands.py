import sys
import attr
from typing import List, Dict, Type, Union
from copy import deepcopy
import logging
from pathlib import Path

from .config import (
    ALL_MINIONS, PRVSNR_USER_FILES_EOSUPDATE_REPOS_DIR,
    PRVSNR_FILEROOTS_DIR, LOCAL_MINION,
    PRVSNR_USER_FILES_SSL_CERTS_FILE
)
from .param import KeyPath, Param
from .pillar import PillarUpdater, PillarResolver
from .api_spec import api_spec
from .salt import (
    StatesApplier, StateFunExecuter, State,
    YumRollbackManager,
    SaltJobsRunner
)
from provisioner import inputs

_mod = sys.modules[__name__]
logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class RunArgsBase:
    targets: str = attr.ib(
        default=ALL_MINIONS,
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "command's host targets"
            }
        }
    )


@attr.s(auto_attribs=True)
class RunArgsUpdate(RunArgsBase):
    dry_run: bool = attr.ib(
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "perform validation only"
            }
        }, default=False
    )


# TODO DRY
@attr.s(auto_attribs=True)
class RunArgsFWUpdate:
    source: str = attr.ib(
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "a path to FW update"
            }
        }
    )
    dry_run: bool = attr.ib(
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "perform validation only"
            }
        }, default=False
    )


@attr.s(auto_attribs=True)
class RunArgsGetResult:
    cmd_id: str = attr.ib(
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "provisioner command ID"
            }
        }
    )


@attr.s(auto_attribs=True)
class RunArgsSSLCerts:
    source: str = attr.ib(
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "ssl certs source"
            }
        }
    )
    restart: bool = attr.ib(
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "restart flag"
            }
        }, default=False
    )
    dry_run: bool = attr.ib(
        metadata={
            inputs.METADATA_ARGPARSER: {
                'help': "perform validation only"
            }
        }, default=False
    )


class CommandParserFillerMixin:
    _run_args_type = RunArgsBase

    @classmethod
    def fill_parser(cls, parser):
        inputs.ParserFiller.fill_parser(cls._run_args_type, parser)

    @classmethod
    def extract_positional_args(cls, kwargs):
        return inputs.ParserFiller.extract_positional_args(
            cls._run_args_type, kwargs
        )

    # TODO tests
    @classmethod
    def pop_run_args(cls, kwargs):
        run_args = cls._run_args_type(
            **{
                k: kwargs.pop(k) for k in list(kwargs)
                if k in attr.fields_dict(cls._run_args_type)
            }
        )
        return run_args


#  - Notes:
#       1. call salt pillar is good since salt will expand
#          properly pillar itself
#       2. if pillar != system state then we are bad
#           - then assume they are in-sync
#  - ? what are cases when pillar != system
#  - ? options to check/ensure sync:
#     - salt.mine
#     - periodical states apply
@attr.s(auto_attribs=True)
class PillarGet(CommandParserFillerMixin):
    params_type: Type[inputs.NoParams] = inputs.NoParams

    # TODO input class type
    @classmethod
    def from_spec(cls):
        return cls()

    def run(self, targets: str = ALL_MINIONS):
        return PillarResolver(targets=targets).pillar


@attr.s(auto_attribs=True)
class Get(CommandParserFillerMixin):
    params_type: Type[inputs.ParamsList] = inputs.ParamsList

    # TODO input class type
    @classmethod
    def from_spec(
        cls, params_type: str = 'ParamsList'
    ):
        return cls(params_type=getattr(inputs, params_type))

    def run(self, *args, **kwargs):
        # TODO tests
        run_args = self.pop_run_args(kwargs)
        params = self.params_type.from_args(*args, **kwargs)
        pillar_resolver = PillarResolver(targets=run_args.targets)
        res_raw = pillar_resolver.get(params)
        res = {}
        for minion_id, data in res_raw.items():
            res[minion_id] = {str(p.name): v for p, v in data.items()}
        return res


# TODO
#   - how to support targetted pillar
#       - per group (grains)
#       - per minion
#       - ...
#
# Implements the following:
#   - update pillar related to some param(s)
#   - call related states (before and after)
#   - rollback if something goes wrong
@attr.s(auto_attribs=True)
class Set(CommandParserFillerMixin):
    # TODO at least either pre or post should be defined
    params_type: Type[
        Union[inputs.ParamGroupInputBase, inputs.ParamDictItemInputBase]
    ]
    pre_states: List[State] = attr.Factory(list)
    post_states: List[State] = attr.Factory(list)

    _run_args_type = RunArgsUpdate

    # TODO input class type
    @classmethod
    def from_spec(
        cls, params_type: str, states: Dict
    ):
        return cls(
            params_type=getattr(inputs, params_type),
            pre_states=[State(state) for state in states.get('pre', [])],
            post_states=[State(state) for state in states.get('post', [])]
        )

    def _run(self, params, targets):
        pillar_updater = PillarUpdater(targets)

        pillar_updater.update(params)
        try:
            StatesApplier.apply(self.pre_states)
            try:
                pillar_updater.apply()
                StatesApplier.apply(self.post_states)
            except Exception:
                logger.exception('Failed to apply changes')
                # TODO more solid rollback
                pillar_updater.rollback()
                pillar_updater.apply()
                raise
        except Exception:
            logger.exception('Failed to apply changes')
            # treat post as restoration for pre, apply
            # if rollback happened
            StatesApplier.apply(self.post_states)
            raise

    # TODO
    # - class for pillar file
    # - caching (load once)
    def run(self, *args, **kwargs):
        run_args = self.pop_run_args(kwargs)

        # static validation
        if len(args) == 1 and isinstance(args[0], self.params_type):
            params = args[0]
        else:
            params = self.params_type.from_args(*args, **kwargs)

        # TODO dynamic validation
        if run_args.dry_run:
            return

        self._run(params, run_args.targets)


# assumtions / limitations
#   - support only for ALL_MINIONS targetting TODO ??? why do you think so
#
#

# set/remove the repo:
#   - call repo reset logic for minions:
#       - remove repo config for yum
#       - unmount repo if needed
#       - remove repo dir/iso file if needed TODO
#   - call repo reset logic for master:
#       - remove local dir/file from salt user file root (if needed)
@attr.s(auto_attribs=True)
class SetEOSUpdateRepo(Set):
    # TODO at least either pre or post should be defined
    params_type: Type[inputs.EOSUpdateRepo] = inputs.EOSUpdateRepo

    # TODO rollback
    def _run(self, params: inputs.EOSUpdateRepo, targets: str):
        # if local - copy the repo to salt user file root
        if params.is_local():
            dest = PRVSNR_USER_FILES_EOSUPDATE_REPOS_DIR / params.release

            # TODO consider to use symlink instead

            if params.is_dir():
                # TODO
                #  - file.recurse expects only dirs from maste file roots
                #    (salt://), need to find another alternative to respect
                #    indempotence
                # StateFunExecuter.execute(
                #     'file.recurse',
                #     fun_kwargs=dict(
                #       source=str(params.source),
                #       name=str(dest)
                #     )
                # )
                StateFunExecuter.execute(
                    'cmd.run',
                    fun_kwargs=dict(
                        name=(
                            "mkdir -p {0} && rm -rf {2} && cp -R {1} {2}"
                            .format(dest.parent, params.source, dest)
                        )
                    )
                )
            else:  # iso file
                StateFunExecuter.execute(
                    'file.managed',
                    fun_kwargs=dict(
                        source=str(params.source),
                        name='{}.iso'.format(dest),
                        makedirs=True
                    )
                )

        # call default set logic (set pillar, call related states)
        super()._run(params, targets)


# TODO consider to use RunArgsUpdate and support dry-run
@attr.s(auto_attribs=True)
class EOSUpdate(CommandParserFillerMixin):
    params_type: Type[inputs.NoParams] = inputs.NoParams

    @classmethod
    def from_spec(cls):
        return cls()

    def run(self, targets):
        # TODO:
        #   - create a state instead
        #   - what about apt and other non-yum pkd managers
        #   (downgrade is another more generic option but it requires
        #    exploration of depednecies that are updated)
        with YumRollbackManager(targets, multiple_targets_ok=True):
            # TODO
            #  - update for provisioner itself
            #  - update for other sw ???
            for component in ('eoscore', 's3server', 'hare', 'sspl', 'csm'):
                state_name = "components.{}.update".format(component)
                try:
                    logger.info("Updating {} on {}".format(component, targets))
                    StatesApplier.apply([state_name], targets)
                except Exception:
                    logger.exception(
                        "Failed to update {} on {}".format(component, targets)
                    )
                    raise


# TODO TEST
@attr.s(auto_attribs=True)
class FWUpdate(CommandParserFillerMixin):
    params_type: Type[inputs.NoParams] = inputs.NoParams
    _run_args_type = RunArgsFWUpdate

    @classmethod
    def from_spec(cls):
        return cls()

    def run(self, source, dry_run=False):
        source = Path(source).resolve()

        if not source.is_file():
            raise ValueError('{} is not a file'.format(source))

        if dry_run:
            return

        script = (
            PRVSNR_FILEROOTS_DIR /
            'components/controller/files/script/controller_cli.sh'
        )
        controller_pi_path = KeyPath('cluster/storage_enclosure/controller')
        ip = Param('ip', 'cluster.sls', controller_pi_path / 'primary_mc/ip')
        user = Param('ip', 'cluster.sls', controller_pi_path / 'user')
        passwd = Param('ip', 'cluster.sls', controller_pi_path / 'password')
        pillar = PillarResolver(LOCAL_MINION).get([ip, user, passwd])
        pillar = next(iter(pillar.values()))

        StateFunExecuter.execute(
            'cmd.run',
            fun_kwargs=dict(
                name=(
                    "{script} host -h {ip} -u {user} -p {passwd} "
                    "--update-fw {source}"
                    .format(
                        script=script,
                        ip=pillar[ip],
                        user=pillar[user],
                        passwd=pillar[passwd],
                        source=source
                    )
                )
            )
        )


@attr.s(auto_attribs=True)
class GetResult(CommandParserFillerMixin):
    params_type: Type[inputs.NoParams] = inputs.NoParams
    _run_args_type = RunArgsGetResult

    @classmethod
    def from_spec(cls):
        return cls()

    def run(self, cmd_id: str):
        return SaltJobsRunner.prvsnr_job_result(cmd_id)

# TODO consider to use RunArgsUpdate and support dry-run
@attr.s(auto_attribs=True)
class SetSSLCerts(CommandParserFillerMixin):
    params_type: Type[inputs.NoParams] = inputs.NoParams
    _run_args_type = RunArgsSSLCerts

    @classmethod
    def from_spec(cls):
        return cls()

    def run(self, source, restart=False, dry_run=False):

        source = Path(source).resolve()

        if not source.is_file():
            raise ValueError('{} is not a file'.format(source))

        if dry_run:
            return

        state_name = "components.misc_pkgs.ssl_certs"
        dest = PRVSNR_USER_FILES_SSL_CERTS_FILE
        # TODO create backup and add timestamp to backups
        StateFunExecuter.execute(
            "file.managed",
            fun_kwargs=dict(
                source=str(source),
                name=str(dest),
                makedirs=True
            )
        )

        try:
            StatesApplier.apply([state_name])
        except Exception:
            logger.exception(
                "Failed to apply certs"
            )
            raise


commands = {}
for command_name, spec in api_spec.items():
    spec = deepcopy(api_spec[command_name])  # TODO
    command = getattr(_mod, spec.pop('type'))
    commands[command_name] = command.from_spec(**spec)
