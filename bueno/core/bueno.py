#
# Copyright (c)      2019 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
The good stuff typically called by __main__.
'''

from bueno import _version

from bueno.core import service
from bueno.core import utils

import argparse
import os
import sys
import traceback
import typing


class ArgumentParser:
    '''
    bueno's argument parser.
    '''
    def __init__(self) -> None:
        self.argp = argparse.ArgumentParser(
            description=self._desc(),
            allow_abbrev=False
        )

    def _desc(self) -> str:
        '''
        Returns the description string for bueno.
        '''
        return 'Utilities for automating reproducible benchmarking.'

    def _addargs(self) -> None:
        self.argp.add_argument(
            '-t', '--traceback',
            help='Provides detailed exception information '
                 'useful for bug reporting and run script debugging.',
            action='store_true',
            default=False,
            required=False
        )
        self.argp.add_argument(
            '-v', '--version',
            help='Displays version information.',
            action='version',
            version='%(prog)s {}'.format(_version.__version__)
        )
        self.argp.add_argument(
            'command',
            # Consume the remaining arguments for command's use.
            nargs=argparse.REMAINDER,
            help='Specifies the command to run '
                 'followed by command-specific arguments.',
            choices=service.Factory.available(),
            action=ArgumentParser.CommandAction
        )

    class CommandAction(argparse.Action):
        '''
        Custom action class used for 'command' argument structure verification.
        '''
        @typing.no_type_check
        def __init__(self, option_strings, dest, nargs, **kwargs):
            super().__init__(option_strings, dest, nargs, **kwargs)

        @typing.no_type_check
        def __call__(self, parser, namespace, values, option_string=None):
            if len(values) == 0:
                help = '{} requires one positional argument (none provided).'
                parser.print_help()
                parser.error(help.format('bueno'))
            setattr(namespace, self.dest, values)

    def parse(self) -> argparse.Namespace:
        self._addargs()

        return self.argp.parse_args()


class Bueno:
    '''
    Implements the bueno service dispatch system.
    '''
    def __init__(self, pargs: argparse.Namespace) -> None:
        service.Factory.build(pargs.command).start()

    @staticmethod
    def main(pargs: argparse.Namespace) -> int:
        try:
            Bueno(pargs)
        except Exception as e:
            print(e)
            if pargs.traceback:
                traceback.print_exc()
            return os.EX_SOFTWARE
        return os.EX_OK


def main() -> int:
    if utils.privileged_user():
        ers = '\nRunning this program as root is a bad idea... Exiting now.\n'
        sys.exit(ers)

    return Bueno.main(ArgumentParser().parse())
