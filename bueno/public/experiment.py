# Copyright (c) 2019-2022 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

# pylint: disable=fixme

'''
Public experiment utilities for good.
'''

import argparse
import ast
import copy
import os
import re
import shlex
import typing

from abc import abstractmethod

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Tuple,
    Type,
    Optional
)

from bueno.core import mathex
from bueno.core import metacls

from bueno.public import data
from bueno.public import host
from bueno.public import logger
from bueno.public import utils


_DEV_NULL: str = '/dev/null'


class _TheExperiment(metaclass=metacls.Singleton):
    '''
    The experiment singleton that encapsulates experiment information.
    '''
    def __init__(self) -> None:
        self._name = 'unnamed-experiment'
        self._output_path = os.getcwd()
        self._foutput = '%n/%u/%d/%h/%i'

    @property
    def name(self) -> str:
        '''
        Returns the experiment's name.
        '''
        return self._name

    @name.setter
    def name(self, names: str) -> None:
        '''
        Sets the experiment's name.
        '''
        if utils.emptystr(names):
            estr = 'Experiment name cannot be empty.'
            raise RuntimeError(estr)
        self._name = names.strip()

    @property
    def output_path(self) -> str:
        '''
        Returns the experiment's base data output path.
        '''
        return self._output_path

    @output_path.setter
    def output_path(self, path: str) -> None:
        '''
        Sets the experiment's base output data path.
        '''
        if utils.emptystr(path):
            estr = 'Experiment base data output path cannot be empty.'
            raise RuntimeError(estr)
        self._output_path = path

    @property
    def foutput(self) -> str:
        '''
        Returns the experiment's formatted data output string.
        '''
        return self._foutput

    @foutput.setter
    def foutput(self, fmt: str) -> None:
        '''
        Sets the experiment's formatted data output string.
        '''
        if utils.emptystr(fmt):
            estr = 'Experiment formatted data string cannot be empty.'
            raise RuntimeError(estr)
        self._foutput = fmt


class _TheFOutputCache(metaclass=metacls.Singleton):
    '''
    The experiment singleton that caches foutput evaluations.
    '''
    def __init__(self) -> None:
        self._fstr = ''
        self._estr = ''
        self._ename = str(name())

    def _eval_fstring(self, fstring: str) -> None:
        self._fstr = fstring
        self._estr = _TheFOutputCache._format_path(fstring)

    def _dirty(self) -> bool:
        # Current experiment name.
        cename = str(name())
        if cename != self._ename:
            self._ename = cename
            return True
        return False

    def path(self, fstring: str) -> str:
        '''
        Returns the appropriate path based on the cache state.
        '''
        if fstring != self._fstr or self._dirty():
            self._eval_fstring(fstring)
        return self._estr

    @staticmethod
    def _format_path(epath: str) -> str:
        '''
        Decodes a path-like string and returns a path if the decoding was
        successful.
        Picture Reference:
        %d - Date
        %h - Hostname
        %i - Unique ID
        %n - Experiment Name
        %t - Time
        %u - User
        '''
        def _get_id_from_path(basep: str) -> str:
            # TODO(skg) The stat load may be huge using this approach.  Fix at
            # some point. Perhaps have a top-level log that gives us the next
            # available? Also, potential for races here.
            maxt = 2048*2048
            for subd in range(0, maxt):
                path = os.path.join(basep, str(subd))
                if not os.path.isdir(path):
                    return str(subd)
            errs = f'Cannot find usable data directory after {maxt} tries.\n' \
                   f'Base output directory searched was: {basep}'
            raise RuntimeError(errs)
        path = epath
        path = path.replace('%d', utils.dates())
        path = path.replace('%t', utils.now().strftime('%H:%M:%S'))
        path = path.replace('%u', host.whoami())
        path = path.replace('%n', str(name()))
        path = path.replace('%h', host.hostname())
        # This needs to be last because we have to stat the base subdirectory to
        # determine the ultimate ID. Scan from left to right to build up IDs as
        # we decode the path.
        idx = path.find('%i')
        while idx != -1:
            path = path.replace('%i', _get_id_from_path(path[0:idx]), 1)
            idx = path.find('%i')

        return path


def flush_data(opath: Optional[str] = None) -> str:
    '''
     Writes cached data to disk at specified or default path rooted at the
     output directory determined at run-time. Returns full path of output.

    '''
    based = str(output_path())
    # Default output path. Should match foutput(), but cached. That way the data
    # are flushed to the same spot by default.
    iopath = str(foutput())
    if opath is not None:
        iopath = opath
    cached_path = _TheFOutputCache().path(iopath)
    real_opath = os.path.join(based, cached_path)
    real_opath = os.path.abspath(real_opath)
    logger.log(f'# Flushing Data to {real_opath}')
    # Clear all cached data because /dev/null was requested as output path.
    if based == _DEV_NULL:
        data.clear()
    else:
        data.write(real_opath)
    return real_opath


class FOM:
    '''
    Figure of Merit data class.
    '''
    def __init__(
            self,
            name: str,  # pylint: disable=redefined-outer-name
            description: str,
            units: str,
            value: float
    ) -> None:
        self.name = name
        self.description = description
        self.units = units
        self.value = float(value)


class CLIAddArgsAction:
    '''
    Base action class used to add additional arguments to a CLIConfiguration
    instance.
    '''
    def __call__(self, clic: 'CLIConfiguration') -> None:
        '''
        Method that shall be used by derived classes to add a custom collection
        of arguments to the calling CLIConfiguration instance via addargs().
        '''
        ers = f'__call__() not defined by {type(self).__name__} subclass.'
        raise NotImplementedError(ers)


class CLIConfiguration:
    '''
    Command-line interface configuration container and associated utilities.
    '''
    def __init__(self, desc: str, argv: List[str]) -> None:
        self._desc = desc
        self._argv = argv
        self._prog = os.path.basename(argv[0])

        self._argprsr = argparse.ArgumentParser(
            prog=self._prog,
            description=self._desc,
            allow_abbrev=False
        )

        self._addargs()
        self._args = argparse.Namespace()

    @property
    def description(self) -> str:
        '''
        Returns the desription used to initialize the encapsulated
        ArgumentParser.
        '''
        return self._desc

    @property
    def argv(self) -> List[str]:
        '''
        Returns the argument list used during instance initialization.
        '''
        return self._argv

    @property
    def program(self) -> str:
        '''
        Returns the basename of argv[0], i.e., the program name.
        '''
        return self._prog

    @property
    def argparser(self) -> argparse.ArgumentParser:
        '''
        Returns the internal ArgumentParser instance.
        '''
        return self._argprsr

    @property
    def args(self) -> argparse.Namespace:
        '''
        Returns the ArgumentParser Namespace acquired after argument parsing.
        '''
        return self._args

    @abstractmethod
    def _addargs(self) -> None:
        '''
        Abstract method that shall be used by derived classes to add a custom
        collection of arguments via self.argparser.add_argument(), for example.
        CLIConfiguration will call this function at the appropriate time.
        '''

    def addargs(self, action: Type[CLIAddArgsAction]) -> None:
        '''
        Instantiates and then calls provided action class to add additional
        arguments to argument parser.
        '''
        action()(self)

    def parseargs(self) -> None:
        '''
        Thin abstraction around argparser.parse_args() that parses and populates
        internal argparse namespace instance.
        '''
        self._args = self.argparser.parse_args(self.argv[1:])

    def update(self, confns: argparse.Namespace) -> None:
        '''
        Update the current configuration using the parsedargs provided through
        confns, a namespace.
        '''
        confd = vars(confns)
        argsd = vars(self.args)
        pcags = vars(parsedargs(self.argparser, self.argv[1:]))
        # Look at the arguments provided in the configuration (gs) file. The
        # order in which the updates occur matters:
        # - confns arguments will overwrite any already set
        # - pcags will overwrite any. This allows the setting of values
        # through a configuration file, while also allowing the ability to
        # overwrite those at run-time through parameters passed to the cli.
        for key, _ in argsd.items():
            if confd[key] is not None:
                argsd[key] = confd[key]
            if pcags[key] is not None:
                argsd[key] = pcags[key]


def name(ename: Optional[str] = None) -> Optional[str]:
    '''
    Experiment name getter/setter. If a name string is provided, then it acts as
    a setter, acting as a getter otherwise.
    '''
    if ename is None:
        return _TheExperiment().name
    if not isinstance(ename, str):
        estr = f'{__name__}.name() expects a string.'
        raise ValueError(estr)
    _TheExperiment().name = ename
    return None


def output_path(path: Optional[str] = None) -> Optional[str]:
    '''
    Experiment data output path getter/setter. If a path is provided, then it
    acts as a setter, acting as a getter otherwise.
    '''
    if path is None:
        return _TheExperiment().output_path
    if not isinstance(path, str):
        estr = f'{__name__}.output_path() expects a string.'
        raise ValueError(estr)
    _TheExperiment().output_path = path
    return None


def generate(spec: str, *args: Any) -> List[str]:
    '''
    Given a string containing string.format() replacement fields and a variable
    number of iterables, attempt to generate an iterable collection of strings
    generated from the provided specification and corresponding inputs.
    '''
    if not isinstance(spec, str):
        estr = f'{__name__}.generate() expects a string specification.'
        raise ValueError(estr)

    argg = zip(* args)

    return [spec.format(*a) for a in argg]


def _expand_all_shell_vars(instr: str) -> str:
    # The regular expression string used to find environment variables.
    res = r'\$\{([^\}]+)\}'
    matches = re.findall(res, instr)
    for match in matches:
        exval = os.getenv(match, default='')
        instr = instr.replace(f'${{{match}}}', exval)
    return instr


def readgs(
        gspath: str,
        config: Optional[CLIConfiguration] = None
) -> Iterable[str]:
    '''
    A convenience routine for reading generate specification files.

    TODO(skg) Add description of formatting rules, semantics, etc. Don't forget
    about yield!

    We accept the following forms:
    # -a/--aarg [ARG_PARAMS] -b/--bargs [ARG PARAMS]
    # -c/--carg [ARG PARAMS] [positional arguments]
    '''
    logger.emlog(f'# Reading Generate Specification File: {gspath}')
    # Emit contents of gs file.
    logger.log('# Begin Generate Specification')
    logger.log(utils.chomp(str().join(utils.cat(gspath))))
    logger.log('# End Generate Specification\n')

    with open(gspath, encoding='utf8') as file:
        argv = []
        lines = [x.strip() for x in utils.read_logical_lines(file)]
        for line in lines:
            # Interpret as special comment used to specify run-time arguments.
            if line.startswith('# -'):
                # Add to argument list.
                if config is not None:
                    argline = _expand_all_shell_vars(line.lstrip('# '))
                    argv.extend(shlex.split(argline))
                continue
            # Skip comments and empty lines.
            if line.startswith('#') or utils.emptystr(line):
                continue
            # Parse arguments if provided an argument parser.
            gsargs = None
            if config is not None:
                if not isinstance(config, CLIConfiguration):
                    estr = f'{__name__} expects an instance of CLIConfiguration'
                    raise ValueError(estr)
                gsargs = parsedargs(config.argparser, argv)
                config.update(gsargs)
            # Not a comment; yield generate specification string.
            yield _expand_all_shell_vars(line)
            # Clear out argument list for next round.
            argv = []


def parsedargs(
        argprsr: argparse.ArgumentParser,
        argv: List[str]
) -> argparse.Namespace:
    '''
    TODO(skg) add a proper description.
    '''
    # Make a deep copy of the provided argument parser.
    auxap = copy.deepcopy(argprsr)
    aargs = auxap.parse_args(argv)
    # Set defaults to None so we can detect setting of arguments.
    nonedefs: Dict[Any, None] = {}
    for key in vars(aargs):
        nonedefs[key] = None
    auxap.set_defaults(**nonedefs)
    # Parse and return the arguments present in argv.
    return auxap.parse_args(argv)


class _CLIArgsAddActions:
    '''
    Container class for custom argparse actions.
    '''
    class RunCmdsAction(argparse.Action):
        '''
        Custom action class used for 'runcmds' argument handling.
        '''
        @typing.no_type_check
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            super().__init__(option_strings, dest, **kwargs)

        @typing.no_type_check
        def __call__(self, parser, namespace, values, option_string=None):
            malf_helps = f'{option_string} malformed input. ' \
                         'An int, int, str, str tuple is excepted.'
            optt = tuple()
            try:
                optt = ast.literal_eval(values)
            except (ValueError, SyntaxError):
                parser.error(malf_helps)
            # Make sure that the evaluated type is tuple.
            if not isinstance(optt, tuple):
                parser.error(malf_helps)
            # Make sure we are dealing with a 4-tuple.
            nopts = len(optt)
            if nopts != 4:
                helps = f'{option_string} requires a 4-tuple of values. ' \
                        f'{nopts} values provided: {optt}.'
                parser.error(helps)
            # Check type of each element.
            if not isinstance(optt[0], int):
                helps = f'{option_string}: The first value must be an int.'
                parser.error(helps)
            if not isinstance(optt[1], int):
                helps = f'{option_string}: The second value must be an int.'
                parser.error(helps)
            if not isinstance(optt[2], str):
                helps = f'{option_string}: The third value must be a string.'
                parser.error(helps)
            if not isinstance(optt[3], str):
                helps = f'{option_string}: The fourth value must be a string.'
                parser.error(helps)
            setattr(namespace, self.dest, optt)


def cli_args_add_runcmds_option(
        clic: CLIConfiguration,
        opt_required: bool = False,
        opt_default: Tuple[int, int, str, str] = (0, 0, '', '')
) -> argparse.Action:
    '''
    Adds parser options to the given CLIConfiguration instance for handling
    runcmds input. Adds --runcmds and a custom action to parse its input.
    '''
    return clic.argparser.add_argument(
        '--runcmds',
        type=str,
        metavar='4TUP',
        help="Specifies the input 4-tuple used to generate run commands. "
             "E.g., \"0, 8, 'srun -n %%n', 'nidx + 1'\"",
        required=opt_required,
        default=opt_default,
        action=_CLIArgsAddActions.RunCmdsAction
    )


class DefaultCLIConfiguration(CLIConfiguration):
    '''
    A 'canned' set of parser arguments common to many (but not all) bueno run
    scripts. This CLI configuration is provided as a convenience for those run
    scripts that can benefit from the options provided.
    '''
    class Defaults:
        '''
        Default values for DefaultCLIConfigurations.
        '''
        csv_output = ''
        description = ''
        executable = ''
        input = ''
        name = ''
        runcmds = (0, 0, '', '')

    def __init__(
            self,
            desc: str,
            argv: List[str],
            defaults: 'DefaultCLIConfiguration.Defaults'
    ) -> None:
        self.defaults = defaults
        super().__init__(desc, argv)

    def _addargs(self) -> None:
        self.argparser.add_argument(
            '-o', '--csv-output',
            type=str,
            metavar='CSV_NAME',
            help='Names the generated CSV file produced by a run.',
            required=False,
            default=self.defaults.csv_output
        )

        self.argparser.add_argument(
            '-d', '--description',
            type=str,
            metavar='DESC',
            help='Describes the experiment.',
            required=False,
            default=self.defaults.description
        )

        self.argparser.add_argument(
            '-e', '--executable',
            type=str,
            metavar='EXEC',
            help="Specifies the executable's path.",
            required=False,
            default=self.defaults.executable
        )

        self.argparser.add_argument(
            '-i', '--input',
            type=str,
            metavar='INP',
            help='Specifies the path to an experiment input file.',
            required=False,
            default=self.defaults.input
        )

        self.argparser.add_argument(
            '-n', '--name',
            type=str,
            help='Names the experiment.',
            required=False,
            default=self.defaults.name
        )
        # Add pre-canned options to deal with experiment.runcmds() input.
        cli_args_add_runcmds_option(
            self,
            opt_required=False,
            opt_default=self.defaults.runcmds
        )


def _runcmds_nargs(line: str, res: str) -> int:
    '''
    Private function that returns the number of arguments found in line given a
    regular expression.
    '''
    nargs = 0
    for _ in re.finditer(res, line, flags=re.X):
        nargs += 1
    return nargs


def runcmds(
        start: int,
        stop: int,
        spec: str,
        nfun: str
) -> List[str]:
    '''
    TODO(skg) Add proper description.
    - start: The start value.
    - stop: The termination value for nfun(nidx) for some value nidx.
    - spec: The run specification template having the following variables:
    -   %n: The number of processes to run.
    '''
    # XXX(skg) I wish we could use something like pylint: disable=W0511
    # __name__ for this...
    fname = 'runcmds'
    # Regex string used to find variables in nfun expressions.
    vidx_res = '''\
    (         # Start of capture group 1
    \\b       # Start of whole word search
    nidx      # Variable literal
    \\b       # End of whole word search
    )         # End of capture group 1
    '''
    # Make sure that the provided stop value make sense.
    if stop < 0:
        estr = f'{__name__}.{fname} start and ' \
               'stop must both be positive values.'
        raise ValueError(estr)
    if start > stop:
        estr = f'{__name__}.{fname} value error: ' \
               'start cannot be less than stop.'
        raise ValueError(estr)
    # Find all variables in the provided function specification string. Also
    # enforce that *at least one* variable is provided.
    if _runcmds_nargs(nfun, vidx_res) == 0:
        # We didn't find at least one variable.
        estr = f'{__name__}.{fname} syntax error: ' \
               'At least one variable must be present. ' \
               F"'nidx' was not found in the following expression:\n{nfun}"
        raise SyntaxError(estr)
    # Generate the requisite values.
    # Notice we include the start value.
    nvals = [start]
    nidx = start
    regex = re.compile(vidx_res, flags=re.X)
    while True:
        nval = mathex.evaluate(regex.sub(str(nidx), nfun))
        if nval > stop:
            break
        nvals.append(nval)
        nidx = nval
    # Now generate the run commands.
    # Regex string used to find %n variables in spec expressions.
    n_res = '%n'
    if _runcmds_nargs(spec, n_res) == 0:
        wstr = F"# WARNING: '{n_res}' not found in " \
               f'the following expression:\n# {spec}'
        logger.emlog(wstr)
    regex = re.compile(n_res)
    cmds = []
    for idx in nvals:
        cmds.append(regex.sub(str(idx), spec))
    return cmds


class _Factor:
    '''
    Provide tools for prime factor combination and
    intellegent recombination
    '''

    def __init__(self, number: int, dimensions: int):
        '''
        Initialize factor instance as specified
        '''
        self.number = number
        self.dimensions = dimensions
        self.factor_list: List[int] = []
        self.prime_list = [
            2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59,
            61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131,
            137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197,
            199, 211, 223, 227, 229, 233, 239, 241, 251, 257, 263, 269, 271,
            277, 281, 283, 293, 307, 311, 313, 317, 331, 337, 347, 349, 353,
            359, 367, 373, 379, 383, 389, 397, 401, 409, 419, 421, 431, 433,
            439, 443, 449, 457, 461, 463, 467, 479, 487, 491, 499, 503, 509,
            521, 523, 541
        ]  # First 100 primes

    def get_prime(self, number: int) -> None:
        '''
        Fill factor_list with prime factors
        '''
        if number in self.prime_list:
            self.factor_list.append(number)
            return  # Is prime; done.

        for value in range(2, int(number/2) + 1):
            if number % value != 0:
                continue  # Not clean division; try next.

            # else, value cleanly divides number
            # append prime factor, repeat with remainder
            self.factor_list.append(value)
            self.get_prime(int(number/value))
            break

    def validate_list(self) -> None:
        '''
        Check factor list total
        '''
        product = 1
        for item in self.factor_list:
            product *= item

        # append unlisted prime if missing
        if self.number != product:
            remainder = int(self.number/product)
            self.factor_list.append(remainder)

    @staticmethod
    def get_root(degree: int, number: int) -> float:
        '''
        Determine the degree root of number
        (nth root of x)
        '''
        return number ** (1.0 / degree)

    def condense_list(self) -> None:
        '''
        Condense factor list to desired dimensions
        '''
        temp_list = self.factor_list
        length = len(temp_list)

        while length > self.dimensions:
            # Case 1: List is 1 item too long
            # Combine the first 2 items
            if length == (self.dimensions + 1):
                alyx = temp_list[0] * temp_list[1]
                temp_list = temp_list[2:]
                temp_list.insert(0, alyx)

                self.factor_list = temp_list
                return  # Done

            # Check for large values
            contains_large = False
            large_val = 0
            for item in temp_list:
                if item >= _Factor.get_root(self.dimensions, self.number):
                    contains_large = True
                    large_val = item

            # Case 2: List contains a large value
            # Combine first and second largest
            if contains_large:
                breen = temp_list[0] * temp_list[length - 2]
                temp_list = temp_list[1:-2]
                temp_list.append(breen)
                temp_list.append(large_val)

                length -= 1

            # Case 3: List is mostly even distribution
            # Combine first and last items
            else:
                calhoun = temp_list[0] * temp_list[length - 1]
                temp_list = temp_list[1:-1]
                temp_list.append(calhoun)

                length -= 1

        # End of while
        # Factor list is <= desired dimension
        if length < self.dimensions:
            buffer = [1] * self.dimensions
            temp_list.extend(buffer)  # Extend to dimension length
            temp_list = temp_list[0: self.dimensions]

        self.factor_list = temp_list
        return  # Done


def factorize(num: int, dim: int) -> List[int]:
    '''
    Perform factor calculations
    '''
    # Get prime factors
    # Validate factor list
    # Recombine factor list
    # Sort factor list (Greatest-Least)

    breakdown = _Factor(num, dim)

    breakdown.get_prime(num)
    breakdown.validate_list()
    breakdown.condense_list()
    breakdown.factor_list.sort(reverse=True)

    return breakdown.factor_list


def foutput(fmtstr: Optional[str] = None) -> Optional[str]:
    '''
    Formatted experiment data string that determines the directory structure
    used to store experimental data. If a name string is provided, then it acts
    as a setter, acting as a getter otherwise.

    Accepts a path-like string and returns a path if the decoding was
    successful.
    Picture Reference:
    %d - Date
    %h - Hostname
    %i - Unique ID
    %n - Experiment Name
    %t - Time
    %u - User
    '''
    if fmtstr is None:
        return _TheExperiment().foutput
    if not isinstance(fmtstr, str):
        estr = f'{__name__}.foutput() expects a string.'
        raise ValueError(estr)
    _TheExperiment().foutput = fmtstr
    return None

# vim: ft=python ts=4 sts=4 sw=4 expandtab
